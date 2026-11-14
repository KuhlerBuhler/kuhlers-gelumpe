/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "defs.h"
#include "sim-main.h"
#include "sim-hw.h"
#include "devices.h"

#define HOST_ENABLE 0x0001
#define HOST_RESET 0x0008
#define READY_OVERRIDE 0x0020
#define TIMEOUT_ENABLE 0x0080
#define DMA_READY 0x0001
#define DMA_COMPLETE 0x0008
#define HANDSHAKE 0x0010
#define HOST_TIMEOUT 0x0020
#define HOST_IRQ 0x0040
#define ALLOW_CONFIG 0x0080
#define TIMEOUT_ENABLED 0x0200
#define READ_DONE 0x8000
#define FIFO_WORDS 16

struct hw *blech_bfin_dma_host_start (struct hw *, bu32, bu16, bool);
void blech_bfin_dma_host_stop (struct hw *, struct hw *, bool);
void blech_bfin_dma_host_check (struct hw *, struct hw *, bool);
void blech_bfin_dma_host_release (struct hw *, struct hw *);
void blech_bfin_dma_request (struct hw *);

struct bfin_hostdp {
  bu32 base;
  struct hw *dma_master;
  bool acked;
  bu16 control, status, timeout;
  bu16 fifo[FIFO_WORDS], configuration[7];
  unsigned head, count, configured;
  struct hw *channel;
  struct hw_event *setup_event;
  bool active, aborted, write;
  bu32 address;
  unsigned words, host_left, dma_left;
};

static void
hostdp_interrupts (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  bool enabled = (host->control & HOST_ENABLE) != 0;
  hw_port_event (me, 0, enabled && (host->status & (HOST_TIMEOUT | HOST_IRQ)));
  hw_port_event (me, 1, enabled && (host->status & READ_DONE));
}

static void
hostdp_fifo_status (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  host->status &= ~6;
  if (!host->count)
    host->status |= 4;
  if (host->count == FIFO_WORDS)
    host->status |= 2;
  hostdp_interrupts (me);
}

static void
hostdp_require_mode (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  if (!(host->control & HOST_ENABLE) || !(host->control & 4)
      || (host->control & (2 | READY_OVERRIDE | TIMEOUT_ENABLE | 0x400)))
    hw_abort (me, "HOSTDP bus requires enabled little-endian 16-bit transfers without burst timing or override");
}

static void
hostdp_memory (struct hw *me, bu32 address, unsigned words, bool write)
{
  SIM_DESC sd = hw_system (me);
  bu64 cursor = address, end = cursor + words * 2U;
  if ((address & 1) || end > 0x100000000ULL)
    hw_abort (me, "invalid HOSTDP DMA memory span");
  while (cursor < end)
    {
      sim_core_mapping *mapping = STATE_CORE (sd)->common.map[write ? write_map : read_map].first;
      while (mapping && !(cursor >= mapping->base && cursor <= mapping->bound))
        mapping = mapping->next;
      if (!mapping || !mapping->buffer || mapping->device || cursor >= 0xFFC00000U)
        hw_abort (me, "HOSTDP DMA target is not mapped memory: %#llx", (unsigned long long) cursor);
      cursor = min (end, (bu64) mapping->bound + 1);
    }
}

static void
hostdp_descriptor (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  const bu16 *words = host->configuration;
  if ((words[0] != 0xA9 && words[0] != 0xAB) || !words[3] || words[3] % FIFO_WORDS
      || words[4] != 2 || words[5] || words[6])
    hw_abort (me, "unsupported HOSTDP descriptor");
  hostdp_memory (me, words[1] | ((bu32) words[2] << 16), words[3], (words[0] & 2) != 0);
}

static void
hostdp_setup (struct hw *me, void *data)
{
  struct bfin_hostdp *host = data;
  host->setup_event = NULL;
  if (!(host->control & HOST_ENABLE))
    return;
  if (host->configured == 7 && !host->active)
    {
      hostdp_require_mode (me);
      hostdp_descriptor (me);
      host->write = (host->configuration[0] & 2) != 0;
      host->address = host->configuration[1] | ((bu32) host->configuration[2] << 16);
      host->words = host->host_left = host->dma_left = host->configuration[3];
      host->channel = blech_bfin_dma_host_start (me, host->address, host->words, host->write);
      if (!host->channel)
        hw_abort (me, "HOSTDP requires DMA1");
      host->active = true;
      host->aborted = false;
      host->configured = 0;
      host->status = (host->status & ~(DMA_COMPLETE | 0x100)) | DMA_READY | (host->write ? 0x100 : 0);
    }
  if (!(host->control & READY_OVERRIDE))
    host->status |= ALLOW_CONFIG;
  hostdp_fifo_status (me);
}

static void
hostdp_schedule (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  if (!host->setup_event)
    host->setup_event = hw_event_queue_schedule (me, 1, hostdp_setup, host);
}

static void
hostdp_reset (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  if (host->setup_event)
    hw_event_queue_deschedule (me, host->setup_event);
  host->setup_event = NULL;
  if (host->channel)
    blech_bfin_dma_host_stop (host->channel, me, false);
  host->channel = NULL;
  host->active = host->aborted = false;
  host->count = host->head = host->configured = 0;
  host->host_left = host->dma_left = 0;
  host->status = 0xC;
}

static void
hostdp_complete (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  if (host->active && !host->aborted && (host->host_left || host->dma_left || host->count))
    hw_abort (me, "HOSTDP completion before the data transfer finished");
  if (host->channel)
    blech_bfin_dma_host_release (host->channel, me);
  host->channel = NULL;
  host->active = host->aborted = false;
  host->status = (host->status & ~DMA_READY) | DMA_COMPLETE;
  if (host->configured == 7)
    hostdp_schedule (me);
  else if ((host->control & HOST_ENABLE) && !(host->control & READY_OVERRIDE))
    host->status |= ALLOW_CONFIG;
}

static void
hostdp_finish_transfer (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  if (host->active && !host->write)
    hw_abort (me, "active read DMA FINISH is not implemented");
  if (!host->active)
    {
      hostdp_reset (me);
      hostdp_schedule (me);
      return;
    }
  if (host->setup_event)
    hw_event_queue_deschedule (me, host->setup_event);
  host->setup_event = NULL;
  host->configured = host->count = host->head = 0;
  host->host_left = host->dma_left = 0;
  host->aborted = true;
  blech_bfin_dma_host_stop (host->channel, me, true);
  host->status |= ALLOW_CONFIG;
  hostdp_fifo_status (me);
}

static void
hostdp_control_word (struct hw *me, bu16 value)
{
  struct bfin_hostdp *host = hw_data (me);
  hostdp_require_mode (me);
  if ((host->configured == 0 || host->configured == 7) && (value & 0xC) == 0xC)
    {
      switch (value & 0xFC)
        {
        case 0x1C: host->status |= HOST_IRQ; break;
        case 0x2C: hostdp_finish_transfer (me); break;
        default:
          if ((value & 0xFC) < 0x3C)
            hw_abort (me, "unsupported HOSTDP control command");
        }
      hostdp_interrupts (me);
      return;
    }
  if (!(host->status & ALLOW_CONFIG) || host->configured == 7)
    hw_abort (me, "HOSTDP configuration is not allowed");
  if (!host->configured && value != 0xA9 && value != 0xAB)
    hw_abort (me, "unsupported HOSTDP configuration word %#x", value);
  host->configuration[host->configured++] = value;
  if (host->configured == 7)
    {
      hostdp_descriptor (me);
      host->status &= ~ALLOW_CONFIG;
      if (!host->active)
        hostdp_schedule (me);
    }
}

static unsigned
hostdp_read (struct hw *me, void *dest, int space, address_word address, unsigned count)
{
  struct bfin_hostdp *host = hw_data (me);
  bu16 value;
  if (!dv_bfin_mmr_require_16_32 (me, address, count, false))
    return 0;
  switch (address - host->base)
    {
    case 0: value = host->control; break;
    case 4: value = host->status; break;
    case 8: value = host->timeout; break;
    default: dv_bfin_mmr_invalid (me, address, count, false); return 0;
    }
  if (count == 2)
    dv_store_2 (dest, value);
  else
    dv_store_4 (dest, value);
  return count;
}

static unsigned
hostdp_write (struct hw *me, const void *source, int space, address_word address, unsigned count)
{
  struct bfin_hostdp *host = hw_data (me);
  bu16 value;
  if (!dv_bfin_mmr_require_16 (me, address, count, true))
    return 0;
  value = dv_load_2 (source);
  switch (address - host->base)
    {
    case 0:
      if ((host->active || host->configured || host->setup_event) && !(value & HOST_RESET)
          && ((host->control ^ value) & (HOST_ENABLE | 2 | 4 | READY_OVERRIDE | TIMEOUT_ENABLE | 0x400)))
        hw_abort (me, "HOSTDP mode changed during an active transfer");
      host->control = value & 0x07E7;
      if (value & HOST_RESET)
        {
          hostdp_reset (me);
          if ((value & HOST_ENABLE) && !(value & READY_OVERRIDE))
            hostdp_schedule (me);
        }
      else if ((value & HOST_ENABLE) && !(value & READY_OVERRIDE) && host->configured < 7)
        host->status |= ALLOW_CONFIG;
      else
        host->status &= ~ALLOW_CONFIG;
      host->status &= ~TIMEOUT_ENABLED;
      if (value & TIMEOUT_ENABLE)
        host->status |= TIMEOUT_ENABLED;
      break;
    case 4:
      host->status &= ~(value & (HOST_TIMEOUT | HOST_IRQ | READ_DONE));
      host->status = (host->status & ~HANDSHAKE) | (value & HANDSHAKE);
      if (value & DMA_COMPLETE)
        hostdp_complete (me);
      break;
    case 8:
      host->timeout = value & 0x07FF;
      break;
    default: dv_bfin_mmr_invalid (me, address, count, true); return 0;
    }
  hostdp_fifo_status (me);
  return count;
}

static const struct hw_port_descriptor hostdp_ports[] = {
  { "stat", 0, 0, output_port },
  { "done", 1, 0, output_port },
  { NULL, 0, 0, 0 }
};

static unsigned
hostdp_dma_read (struct hw *me, void *dest, int space, unsigned_word address, unsigned count)
{
  struct bfin_hostdp *host = hw_data (me);
  unsigned done = 0;
  if (!host->active || host->aborted || !host->write || host->dma_master != host->channel)
    hw_abort (me, "HOSTDP DMA read without the owning write descriptor");
  blech_bfin_dma_host_check (host->channel, me, true);
  if (!count || (count & 1) || address != host->address + (host->words - host->dma_left) * 2U)
    hw_abort (me, "invalid HOSTDP DMA read span");
  while (done < count && host->count && host->dma_left)
    {
      dv_store_2 ((bu8 *) dest + done, host->fifo[host->head]);
      host->head = (host->head + 1) % FIFO_WORDS;
      --host->count;
      --host->dma_left;
      done += 2;
    }
  hostdp_fifo_status (me);
  return done;
}

static unsigned
hostdp_dma_write (struct hw *me, const void *source, int space, unsigned_word address,
                  unsigned count, int violate_read_only_section)
{
  struct bfin_hostdp *host = hw_data (me);
  unsigned done = 0;
  if (!host->active || host->aborted || host->write || host->dma_master != host->channel)
    hw_abort (me, "HOSTDP DMA write without the owning read descriptor");
  blech_bfin_dma_host_check (host->channel, me, false);
  if (!count || (count & 1) || address != host->address + (host->words - host->dma_left) * 2U)
    hw_abort (me, "invalid HOSTDP DMA write span");
  while (done < count && host->count < FIFO_WORDS && host->dma_left)
    {
      host->fifo[(host->head + host->count) % FIFO_WORDS] = dv_load_2 ((const bu8 *) source + done);
      ++host->count;
      --host->dma_left;
      done += 2;
    }
  hostdp_fifo_status (me);
  return done;
}

static void
hostdp_finish (struct hw *me)
{
  struct bfin_hostdp *host = HW_ZALLOC (me, struct bfin_hostdp);
  reg_property_spec reg;
  int space;
  address_word base;
  unsigned size;
  if (!hw_find_reg_array_property (me, "reg", 0, &reg))
    hw_abort (me, "HOSTDP requires a register region");
  hw_unit_address_to_attach_address (hw_parent (me), &reg.address, &space, &base, me);
  hw_unit_size_to_attach_size (hw_parent (me), &reg.size, &size, me);
  if (size != 12)
    hw_abort (me, "HOSTDP register region must have size 12");
  host->base = base;
  host->control = 0x0400;
  host->status = 0x000C;
  set_hw_data (me, host);
  set_hw_io_read_buffer (me, hostdp_read);
  set_hw_io_write_buffer (me, hostdp_write);
  set_hw_dma_read_buffer (me, hostdp_dma_read);
  set_hw_dma_write_buffer (me, hostdp_dma_write);
  set_hw_ports (me, hostdp_ports);
  hw_attach_address (hw_parent (me), 0, space, base, size, me);
}

const struct hw_descriptor dv_bfin_hostdp_descriptor[] = {
  { "bfin_hostdp", hostdp_finish },
  { NULL, NULL }
};

int blech_bfin_hostdp_event (SIM_DESC, unsigned);
int blech_bfin_hostdp_bus (SIM_DESC, unsigned, bu32 *);
int blech_bfin_hostdp_dma_enabled (struct hw *);

int
blech_bfin_hostdp_dma_enabled (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  return (host->control & HOST_ENABLE) != 0;
}

int
blech_bfin_hostdp_bus (SIM_DESC sd, unsigned operation, bu32 *word)
{
  struct hw *me;
  struct bfin_hostdp *host;
  if (STATE_ENVIRONMENT (sd) != OPERATING_ENVIRONMENT || operation > 3)
    return 0;
  me = hw_tree_find_device (sim_hw_parse (sd, "/core"), "./bfin_hostdp");
  if (!me)
    return 0;
  host = hw_data (me);
  if (operation == 0)
    {
      *word = host->status;
      return 1;
    }
  if (*word > 65535)
    return 0;
  hostdp_require_mode (me);
  if (operation == 1)
    hostdp_control_word (me, *word);
  else if (operation == 2)
    {
      if (!host->active || host->aborted || !host->write || !host->host_left
          || !(host->control & 0x100) || host->count == FIFO_WORDS)
        hw_abort (me, "HOSTDP data write is not allowed or FIFO is full");
      host->fifo[(host->head + host->count) % FIFO_WORDS] = *word;
      ++host->count;
      --host->host_left;
      blech_bfin_dma_request (host->channel);
    }
  else
    {
      if (!host->active || host->aborted || host->write || !host->host_left
          || !(host->control & 0x200) || !host->count)
        hw_abort (me, "HOSTDP data read is not allowed or FIFO is empty");
      *word = host->fifo[host->head];
      host->head = (host->head + 1) % FIFO_WORDS;
      --host->count;
      --host->host_left;
      if (!host->host_left)
        host->status |= READ_DONE;
      blech_bfin_dma_request (host->channel);
    }
  hostdp_fifo_status (me);
  return 1;
}

int
blech_bfin_hostdp_event (SIM_DESC sd, unsigned event)
{
  struct hw *me;
  struct bfin_hostdp *host;
  if (STATE_ENVIRONMENT (sd) != OPERATING_ENVIRONMENT || event < 1 || event > 3)
    return 0;
  me = hw_tree_find_device (sim_hw_parse (sd, "/core"), "./bfin_hostdp");
  if (me == NULL)
    return 0;
  host = hw_data (me);
  if (!(host->control & HOST_ENABLE)
      || (event == 2 && !(host->control & TIMEOUT_ENABLE)))
    return 0;
  host->status |= event == 1 ? HOST_IRQ : event == 2 ? HOST_TIMEOUT : READ_DONE;
  hostdp_interrupts (me);
  return 1;
}

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

struct bfin_hostdp {
  bu32 base;
  bu16 control, status, timeout;
};

static void
hostdp_interrupts (struct hw *me)
{
  struct bfin_hostdp *host = hw_data (me);
  bool enabled = (host->control & HOST_ENABLE) != 0;
  hw_port_event (me, 0, enabled && (host->status & (HOST_TIMEOUT | HOST_IRQ)));
  hw_port_event (me, 1, enabled && (host->status & READ_DONE));
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
      host->control = value & 0x07E7;
      if (value & HOST_RESET)
        host->status = 0x000C;
      else if ((value & HOST_ENABLE) && !(value & READY_OVERRIDE))
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
        host->status = (host->status & ~DMA_READY) | DMA_COMPLETE;
      break;
    case 8:
      host->timeout = value & 0x07FF;
      break;
    default: dv_bfin_mmr_invalid (me, address, count, true); return 0;
    }
  hostdp_interrupts (me);
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
  hw_abort (me, "HOSTDP DMA read is not implemented");
}

static unsigned
hostdp_dma_write (struct hw *me, const void *source, int space, unsigned_word address,
                  unsigned count, int violate_read_only_section)
{
  hw_abort (me, "HOSTDP DMA write is not implemented");
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

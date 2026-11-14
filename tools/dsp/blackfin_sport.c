/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "defs.h"
#include "sim-main.h"
#include "sim-hw.h"
#include "devices.h"

#define RX_NOT_EMPTY 0x01
#define RX_UNDERFLOW 0x02
#define RX_OVERFLOW 0x04
#define TX_FULL 0x08
#define TX_UNDERFLOW 0x10
#define TX_OVERFLOW 0x20
#define TX_HOLD_EMPTY 0x40
#define ERRORS (RX_UNDERFLOW | RX_OVERFLOW | TX_UNDERFLOW | TX_OVERFLOW)
#define WORDS_PER_FRAME 4
#define FIFO_WORDS 4

void blech_bfin_dma_request (struct hw *);
void blech_bfin_dma_sport_check (struct hw *, bool);

struct sport_fifo {
  bu32 words[FIFO_WORDS];
  unsigned head, count;
};

struct bfin_sport {
  bu32 base;
  struct hw *dma_master;
  bool acked;
  bu32 regs[24];
  struct sport_fifo rx, tx;
  struct hw *rx_dma, *tx_dma;
  struct hw_event *tick;
  bu32 core_hz, rate, mode, seed, lcg, remainder;
  bu32 rx_frames, tx_frames, rx_words, tx_words, tx_hash, last_rx;
};

static void
fifo_put (struct sport_fifo *fifo, bu32 value)
{
  fifo->words[(fifo->head + fifo->count) % FIFO_WORDS] = value;
  ++fifo->count;
}

static bu32
fifo_get (struct sport_fifo *fifo)
{
  bu32 value = fifo->words[fifo->head];
  fifo->head = (fifo->head + 1) % FIFO_WORDS;
  --fifo->count;
  return value;
}

static void
sport_status (struct hw *me)
{
  struct bfin_sport *sport = hw_data (me);
  sport->regs[12] &= ERRORS;
  if (sport->rx.count)
    sport->regs[12] |= RX_NOT_EMPTY;
  if (sport->tx.count == FIFO_WORDS)
    sport->regs[12] |= TX_FULL;
  if (!sport->tx.count)
    sport->regs[12] |= TX_HOLD_EMPTY;
  hw_port_event (me, DV_PORT_STAT, (sport->regs[12] & ERRORS) != 0);
}

static void sport_tick (struct hw *, void *);

static void
sport_schedule (struct hw *me)
{
  struct bfin_sport *sport = hw_data (me);
  unsigned delay;
  sport->remainder += sport->core_hz % sport->rate;
  delay = sport->core_hz / sport->rate;
  if (sport->remainder >= sport->rate)
    {
      sport->remainder -= sport->rate;
      ++delay;
    }
  sport->tick = hw_event_queue_schedule (me, delay, sport_tick, sport);
}

static void
sport_tick (struct hw *me, void *data)
{
  struct bfin_sport *sport = data;
  unsigned i;
  sport->tick = NULL;
  if (sport->regs[8] & 1)
    {
      ++sport->rx_frames;
      for (i = 0; i < WORDS_PER_FRAME; ++i)
        {
          bu32 value = 0;
          if (sport->mode)
            value = sport->lcg = sport->lcg * 1664525U + 1013904223U;
          if (sport->rx.count < FIFO_WORDS)
            fifo_put (&sport->rx, value);
          else
            sport->regs[12] |= RX_OVERFLOW;
        }
      if (sport->rx_dma)
        blech_bfin_dma_request (sport->rx_dma);
    }
  if (sport->regs[0] & 1)
    {
      ++sport->tx_frames;
      for (i = 0; i < WORDS_PER_FRAME; ++i)
        {
          bu32 value = 0;
          unsigned byte;
          if (sport->tx.count)
            {
              value = fifo_get (&sport->tx);
              ++sport->tx_words;
            }
          else
            sport->regs[12] |= TX_UNDERFLOW;
          for (byte = 0; byte < 4; ++byte)
            sport->tx_hash = (sport->tx_hash ^ ((value >> (byte * 8)) & 255)) * 16777619U;
        }
      if (sport->tx_dma)
        blech_bfin_dma_request (sport->tx_dma);
    }
  sport_status (me);
  if ((sport->regs[0] | sport->regs[8]) & 1)
    sport_schedule (me);
}

static void
sport_enable (struct hw *me, unsigned index, bu16 value)
{
  struct bfin_sport *sport = hw_data (me);
  bool was_enabled = (sport->regs[index] & 1) != 0;
  if (value & 1)
    {
      bu16 format = value & ~5;
      if (!sport->core_hz)
        hw_abort (me, "SPORT0 requires an explicitly configured test clock");
      if (format != 0x4400 || (!index && (value & 4))
          || sport->regs[index + 1] != 0x031F
          || sport->regs[14] || sport->regs[15])
        hw_abort (me, "unsupported SPORT0 format: CR1=%#x CR2=%#x MCMC1=%#x MCMC2=%#x",
                  value, sport->regs[index + 1], sport->regs[14], sport->regs[15]);
    }
  if (was_enabled)
    sport->regs[index] = (sport->regs[index] & ~1) | (value & 1);
  else
    sport->regs[index] = value;
  if (!(value & 1))
    {
      struct sport_fifo *fifo = index ? &sport->rx : &sport->tx;
      fifo->head = fifo->count = 0;
      sport->regs[12] &= ~(index ? RX_OVERFLOW | RX_UNDERFLOW : TX_OVERFLOW | TX_UNDERFLOW);
    }
  if ((sport->regs[0] | sport->regs[8]) & 1)
    {
      if (!sport->tick)
        sport_schedule (me);
    }
  else if (sport->tick)
    {
      hw_event_queue_deschedule (me, sport->tick);
      sport->tick = NULL;
      sport->remainder = 0;
    }
  sport_status (me);
}

static unsigned
sport_read (struct hw *me, void *dest, int space, address_word address, unsigned count)
{
  struct bfin_sport *sport = hw_data (me);
  unsigned off = address - sport->base;
  bu32 value;
  if (!dv_bfin_mmr_require_16_32 (me, address, count, false))
    return 0;
  if (off == 0x10 || off == 0x14 || off == 0x1C || off >= 0x60 || (off & 3))
    {
      dv_bfin_mmr_invalid (me, address, count, false);
      return 0;
    }
  if (off == 0x18)
    {
      if (count != 4)
        hw_abort (me, "SPORT0 supports only 32-bit data words");
      if (sport->rx.count)
        sport->last_rx = fifo_get (&sport->rx);
      else
        sport->regs[12] |= RX_UNDERFLOW;
      value = sport->last_rx;
    }
  else
    value = sport->regs[off / 4];
  if (count == 2)
    dv_store_2 (dest, value);
  else
    dv_store_4 (dest, value);
  sport_status (me);
  return count;
}

static unsigned
sport_write (struct hw *me, const void *source, int space, address_word address, unsigned count)
{
  struct bfin_sport *sport = hw_data (me);
  unsigned off = address - sport->base;
  bu32 value;
  if (off >= 0x60 || (off & 3) || off == 0x14 || off == 0x18 || off == 0x1C)
    {
      dv_bfin_mmr_invalid (me, address, count, true);
      return 0;
    }
  if (off == 0x10 || off >= 0x40)
    {
      if (!dv_bfin_mmr_require_32 (me, address, count, true))
        return 0;
      value = dv_load_4 (source);
    }
  else
    {
      if (!dv_bfin_mmr_require_16 (me, address, count, true))
        return 0;
      value = dv_load_2 (source);
    }
  if (off == 0 || off == 0x20)
    sport_enable (me, off / 4, value);
  else if (off == 0x10)
    {
      if (sport->tx.count < FIFO_WORDS)
        fifo_put (&sport->tx, value);
      else
        sport->regs[12] |= TX_OVERFLOW;
    }
  else if (off == 0x30)
    sport->regs[12] &= ~(value & ERRORS);
  else if (off != 0x34)
    {
      unsigned cr = off < 0x20 ? 0 : 8;
      bool active = off >= 0x38 ? ((sport->regs[0] | sport->regs[8]) & 1)
                                 : (sport->regs[cr] & 1);
      if (!active)
        sport->regs[off / 4] = value;
    }
  sport_status (me);
  return count;
}

static unsigned
sport_dma_read (struct hw *me, void *dest, int space, unsigned_word address, unsigned count)
{
  struct bfin_sport *sport = hw_data (me);
  unsigned done = 0;
  if (!sport->dma_master)
    hw_abort (me, "SPORT0 DMA read requires a channel");
  blech_bfin_dma_sport_check (sport->dma_master, true);
  sport->rx_dma = sport->dma_master;
  if (!count || (count & 3))
    hw_abort (me, "unsupported SPORT0 DMA read size %u", count);
  if (sport->regs[8] & 1)
    while (done < count && sport->rx.count)
      {
        dv_store_4 ((bu8 *) dest + done, fifo_get (&sport->rx));
        done += 4;
        ++sport->rx_words;
      }
  sport_status (me);
  return done;
}

static unsigned
sport_dma_write (struct hw *me, const void *source, int space, unsigned_word address,
                 unsigned count, int violate_read_only_section)
{
  struct bfin_sport *sport = hw_data (me);
  unsigned done = 0;
  if (!sport->dma_master)
    hw_abort (me, "SPORT0 DMA write requires a channel");
  blech_bfin_dma_sport_check (sport->dma_master, false);
  sport->tx_dma = sport->dma_master;
  if (!count || (count & 3))
    hw_abort (me, "unsupported SPORT0 DMA write size %u", count);
  if (sport->regs[0] & 1)
    while (done < count && sport->tx.count < FIFO_WORDS)
      {
        fifo_put (&sport->tx, dv_load_4 ((const bu8 *) source + done));
        done += 4;
      }
  sport_status (me);
  return done;
}

static const struct hw_port_descriptor sport_ports[] = {
  { "tx", DV_PORT_TX, 0, output_port },
  { "rx", DV_PORT_RX, 0, output_port },
  { "stat", DV_PORT_STAT, 0, output_port },
  { NULL, 0, 0, 0 }
};

static void
sport_finish (struct hw *me)
{
  struct bfin_sport *sport = HW_ZALLOC (me, struct bfin_sport);
  reg_property_spec reg;
  int space;
  address_word base;
  unsigned size;
  if (!hw_find_reg_array_property (me, "reg", 0, &reg))
    hw_abort (me, "SPORT0 requires a register region");
  hw_unit_address_to_attach_address (hw_parent (me), &reg.address, &space, &base, me);
  hw_unit_size_to_attach_size (hw_parent (me), &reg.size, &size, me);
  if (size != 0x60)
    hw_abort (me, "SPORT0 register region must have size 0x60");
  sport->base = base;
  sport->regs[12] = TX_HOLD_EMPTY;
  set_hw_data (me, sport);
  set_hw_io_read_buffer (me, sport_read);
  set_hw_io_write_buffer (me, sport_write);
  set_hw_dma_read_buffer (me, sport_dma_read);
  set_hw_dma_write_buffer (me, sport_dma_write);
  set_hw_ports (me, sport_ports);
  hw_attach_address (hw_parent (me), 0, space, base, size, me);
}

const struct hw_descriptor dv_bfin_sport_descriptor[] = {
  { "bfin_sport", sport_finish },
  { NULL, NULL }
};

int blech_bfin_sport_config (SIM_DESC, bu32, bu32, bu32, bu32);
int blech_bfin_sport_report (SIM_DESC, bu32 *);

static struct bfin_sport *
sport_device (SIM_DESC sd)
{
  struct hw *me;
  if (STATE_ENVIRONMENT (sd) != OPERATING_ENVIRONMENT)
    return NULL;
  me = hw_tree_find_device (sim_hw_parse (sd, "/core"), "./bfin_sport@0");
  return me ? hw_data (me) : NULL;
}

int
blech_bfin_sport_config (SIM_DESC sd, bu32 core_hz, bu32 rate, bu32 mode, bu32 seed)
{
  struct bfin_sport *sport = sport_device (sd);
  if (!sport || sport->core_hz || core_hz < 48000 || core_hz > 2000000000 || rate != 48000 || mode > 1
      || ((sport->regs[0] | sport->regs[8]) & 1))
    return 0;
  sport->core_hz = core_hz;
  sport->rate = rate;
  sport->mode = mode;
  sport->seed = sport->lcg = seed;
  sport->rx_frames = sport->tx_frames = sport->rx_words = sport->tx_words = 0;
  sport->tx_hash = 2166136261U;
  sport->remainder = 0;
  return 1;
}

int
blech_bfin_sport_report (SIM_DESC sd, bu32 *report)
{
  struct bfin_sport *sport = sport_device (sd);
  if (!sport)
    return 0;
  report[0] = sport->core_hz;
  report[1] = sport->rate;
  report[2] = sport->mode;
  report[3] = sport->seed;
  report[4] = sport->lcg;
  report[5] = sport->rx_frames;
  report[6] = sport->tx_frames;
  report[7] = sport->rx_words;
  report[8] = sport->tx_words;
  report[9] = sport->tx_hash;
  report[10] = sport->rx.count;
  report[11] = sport->tx.count;
  return 1;
}

#include "sim-hw.h"

void blech_bfin_dma_request (struct hw *);
void blech_bfin_dma_sport_check (struct hw *, bool);
struct hw *blech_bfin_dma_host_start (struct hw *, bu32, bu16, bool);
void blech_bfin_dma_host_stop (struct hw *, struct hw *, bool);
void blech_bfin_dma_host_check (struct hw *, struct hw *, bool);
void blech_bfin_dma_host_release (struct hw *, struct hw *);

void
blech_bfin_dma_request (struct hw *me)
{
  struct bfin_dma *dma = hw_data (me);
  if (bfin_dma_enabled (dma) && bfin_dma_running (dma))
    bfin_dma_reschedule (me, 1);
}

void
blech_bfin_dma_sport_check (struct hw *me, bool receive)
{
  struct bfin_dma *dma;
  dma = hw_data (me);
  if (dma->ele_size != 4 || (dma->config & WDSIZE) != WDSIZE_32
      || (dma->start_addr & 3) || dma->x_modify != 4 || (dma->config & DMA2D)
      || (dma->peripheral_map >> 12) != (receive ? 3 : 4)
      || !dma->x_count || (dma->x_count % 4)
      || ((dma->config & DMAFLOW) != DMAFLOW_STOP
          && (dma->config & DMAFLOW) != DMAFLOW_AUTO
          && ((dma->config & DMAFLOW) != DMAFLOW_LARGE
              || (dma->config & NDSIZE) != NDSIZE_6)))
    hw_abort (me, "unsupported SPORT0 DMA transfer: config=%#x count=%u modify=%d",
              dma->config, dma->x_count, dma->x_modify);
}

struct hw *
blech_bfin_dma_host_start (struct hw *owner, bu32 address, bu16 count, bool write)
{
  SIM_DESC sd = hw_system (owner);
  struct hw *me = hw_tree_find_device (sim_hw_parse (sd, "/core"), "./bfin_dmac@0/bfin_dma@1");
  struct bfin_dma *dma;
  if (!me)
    return NULL;
  dma = hw_data (me);
  if (bfin_dma_running (dma) || dma->peripheral_map != 0x1000)
    hw_abort (me, "HOSTDP cannot claim busy or remapped DMA1");
  bfin_dma_reschedule (me, 0);
  dma->hw_peer = NULL;
  dma->host_owner = owner;
  dma->start_addr = address;
  dma->next_desc_ptr = 0;
  dma->x_count = count;
  dma->x_modify = 2;
  dma->y_count = dma->y_modify = 0;
  dma->config = DMAEN | WDSIZE_16 | (write ? WNR | DI_EN : 0);
  dma->irq_status = DMA_RUN;
  hw_port_event (me, 0, 0);
  bfin_dma_process_desc (me, dma);
  bfin_dma_reschedule (me, 1);
  return me;
}

void
blech_bfin_dma_host_stop (struct hw *me, struct hw *owner, bool notify)
{
  struct bfin_dma *dma = hw_data (me);
  if (dma->host_owner != owner)
    hw_abort (me, "HOSTDP cannot stop a replaced DMA descriptor");
  bfin_dma_reschedule (me, 0);
  dma->config &= ~DMAEN;
  dma->irq_status &= ~(DMA_RUN | DMA_DONE | DMA_ERR);
  if (notify)
    dma->irq_status |= DMA_DONE;
  dma->hw_peer = NULL;
  hw_port_event (me, 0, notify && (dma->config & DI_EN));
  if (!notify)
    dma->host_owner = NULL;
}

void
blech_bfin_dma_host_check (struct hw *me, struct hw *owner, bool write)
{
  struct bfin_dma *dma = hw_data (me);
  bu16 expected = DMAEN | WDSIZE_16 | (write ? WNR | DI_EN : 0);
  if (dma->host_owner != owner || dma->config != expected || dma->peripheral_map != 0x1000
      || dma->ele_size != 2 || dma->x_modify != 2)
    hw_abort (me, "HOSTDP DMA1 configuration changed during a transfer");
}

void
blech_bfin_dma_host_release (struct hw *me, struct hw *owner)
{
  struct bfin_dma *dma = hw_data (me);
  if (dma->host_owner != owner || bfin_dma_running (dma))
    hw_abort (me, "HOSTDP cannot release an unfinished or replaced DMA descriptor");
  dma->host_owner = NULL;
}

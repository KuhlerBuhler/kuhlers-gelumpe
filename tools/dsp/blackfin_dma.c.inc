void blech_bfin_dma_request (struct hw *);
void blech_bfin_dma_sport_check (struct hw *, bool);

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

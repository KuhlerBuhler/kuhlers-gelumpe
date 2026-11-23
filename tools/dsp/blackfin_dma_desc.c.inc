/* SPDX-License-Identifier: GPL-3.0-or-later */
static void
bfin_dma_process_desc (struct hw *me, struct bfin_dma *dma)
{
  bu16 flow = dma->config & DMAFLOW;
  unsigned words = (dma->config & NDSIZE) >> NDSIZE_SHIFT;
  unsigned skip = 0, index;
  bu32 address = flow == DMAFLOW_ARRAY ? dma->curr_desc_ptr : dma->next_desc_ptr;
  bu16 values[9];
  bu16 *stores[] = {
    &dma->sal, &dma->sah, &dma->config, &dma->x_count,
    (void *) &dma->x_modify, &dma->y_count, (void *) &dma->y_modify,
  };

  HW_TRACE ((me, "dma starting up %#x", dma->config));
  switch (flow)
    {
    case DMAFLOW_STOP:
    case DMAFLOW_AUTO:
      if (words)
        hw_abort (me, "DMA config error: DMAFLOW_{AUTO,STOP} requires NDSIZE_0");
      break;
    case DMAFLOW_ARRAY:
      if (!words || words > 7)
        hw_abort (me, "DMA config error: DMAFLOW_ARRAY requires NDSIZE 1...7");
      break;
    case DMAFLOW_SMALL:
      if (!words || words > 8)
        hw_abort (me, "DMA config error: DMAFLOW_SMALL requires NDSIZE 1...8");
      skip = 1;
      break;
    case DMAFLOW_LARGE:
      if (words < 2 || words > 9)
        hw_abort (me, "DMA config error: unsupported DMAFLOW_LARGE descriptor size (need 2...9)");
      skip = 2;
      break;
    default:
      hw_abort (me, "DMA config error: invalid DMAFLOW %#x", dma->config);
    }

  dma->active_desc_ptr = 0;
  if (words)
    {
      if (address & 1)
        hw_abort (me, "unaligned DMA descriptor at %#x", address);
      if (sim_read (hw_system (me), address, values, words * 2) != words * 2)
        hw_abort (me, "DMA descriptor fetch failed at %#x", address);
      if (skip)
        {
          dma->ndpl = values[0];
          if (skip == 2)
            dma->ndph = values[1];
        }
      for (index = skip; index < words; ++index)
        *stores[index - skip] = values[index];
      dma->active_desc_ptr = address;
      dma->curr_desc_ptr = address + words * 2;
    }

  if (!(dma->config & DMAEN))
    {
      dma->irq_status &= ~DMA_RUN;
      return;
    }

  switch (dma->config & WDSIZE)
    {
    case WDSIZE_8: dma->ele_size = 1; break;
    case WDSIZE_16: dma->ele_size = 2; break;
    case WDSIZE_32: dma->ele_size = 4; break;
    default: hw_abort (me, "invalid DMA word size");
    }
  if (dma->start_addr & (dma->ele_size - 1))
    hw_abort (me, "unaligned DMA data address %#x", dma->start_addr);
  if (dma->ele_size != (unsigned) abs (dma->x_modify))
    hw_abort (me, "DMA config (striding) %#x not supported (x_modify: %d)",
              dma->config, dma->x_modify);
  if ((dma->config & DMA2D) && dma->x_count == 1)
    hw_abort (me, "invalid 2-D DMA inner count");
  dma->curr_addr = dma->start_addr;
  dma->curr_x_count = dma->x_count;
  dma->curr_y_count = dma->y_count;
}

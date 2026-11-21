/* SPDX-License-Identifier: GPL-3.0-or-later */
static struct {
  bu64 begin, end;
  struct {
    bu64 accesses, bytes;
    bu32 address, origin, descriptor, width;
  } rows[4];
} blech_memory;

int
blech_bfin_memory_window (bu32 address, bu32 length)
{
  if ((bu64) address + length > 0x100000000ULL)
    return 0;
  memset (&blech_memory, 0, sizeof (blech_memory));
  blech_memory.begin = address;
  blech_memory.end = (bu64) address + length;
  return 1;
}

void
blech_bfin_memory_access (unsigned kind, bu32 address, unsigned length,
                          bu32 origin, bu32 descriptor)
{
  bu64 begin = blech_memory.begin > address ? blech_memory.begin : address;
  bu64 end = blech_memory.end < (bu64) address + length
            ? blech_memory.end : (bu64) address + length;
  if (kind >= 4 || begin >= end)
    return;
  ++blech_memory.rows[kind].accesses;
  blech_memory.rows[kind].bytes += end - begin;
  blech_memory.rows[kind].address = address;
  blech_memory.rows[kind].origin = origin;
  blech_memory.rows[kind].descriptor = descriptor;
  blech_memory.rows[kind].width = length;
}

void
blech_bfin_memory_report (bu64 *counts, bu32 *locations)
{
  unsigned i;
  for (i = 0; i < 4; ++i)
    {
      counts[2 * i] = blech_memory.rows[i].accesses;
      counts[2 * i + 1] = blech_memory.rows[i].bytes;
      locations[4 * i] = blech_memory.rows[i].address;
      locations[4 * i + 1] = blech_memory.rows[i].origin;
      locations[4 * i + 2] = blech_memory.rows[i].descriptor;
      locations[4 * i + 3] = blech_memory.rows[i].width;
    }
}

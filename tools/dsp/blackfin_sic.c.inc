static bu32
blech_sic_levels (struct hw *me, bu32 isr, bu32 imask, const bu32 *iar)
{
  bu32 levels = 0, pending = isr & imask;
  unsigned pin;
  for (pin = 0; pin < 32; ++pin)
    if (pending & (1U << pin))
      {
        unsigned route = (iar[pin / 8] >> ((pin % 8) * 4)) & 15;
        if (route > 8)
          hw_abort (me, "invalid BF52x interrupt route %u", route);
        levels |= 1U << (IVG7 + route);
      }
  return levels;
}

static void
bfin_sic_52x_forward_interrupts (struct hw *me, struct bfin_sic *sic)
{
  bu32 levels = blech_sic_levels (me, sic->bf52x.isr0, sic->bf52x.imask0, &sic->bf52x.iar0)
                | blech_sic_levels (me, sic->bf52x.isr1, sic->bf52x.imask1, &sic->bf52x.iar4);
  bu32 changed = sic->system_lines ^ levels;
  unsigned ivg;
  sic->system_lines = levels;
  for (ivg = IVG7; ivg <= IVG15; ++ivg)
    if (changed & (1U << ivg))
      hw_port_event (me, ivg, (levels & (1U << ivg)) != 0);
}

; The blue Electribe has no SAMPLE EDIT: the level CATEGORY (script_sample_edit.s) is never entered and its counter never counts.
menu_counter_se:
    bx lr
menu_se_next:
menu_se_page:
    pop {r4, pc}
menu_text_se:
    b menu_text_look_line3
menu_value_se:
    b menu_value_done
se_tab:
    .word str_tab_du

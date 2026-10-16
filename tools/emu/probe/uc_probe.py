"""Which Unicorn setups survive on this system: main thread or a worker thread, small or large mappings."""
import faulthandler
import sys
import threading

faulthandler.enable()
import unicorn  # noqa: E402

def attempt(label, size, cpu=True):
    uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
    if cpu:
        uc.ctl_set_cpu_model(unicorn.arm_const.UC_CPU_ARM_926)
    uc.mem_map(0xC0000000, size, unicorn.UC_PROT_ALL)
    uc.mem_write(0xC0000000, b"\x00" * 16)
    print(label, hex(size), "ok", flush=True)

def in_thread(label, size, cpu=True, stack=None):
    if stack:
        threading.stack_size(stack)
    t = threading.Thread(target=attempt, args=(label, size, cpu))
    t.start()
    t.join()

mode = sys.argv[1] if len(sys.argv) > 1 else "all"
print("unicorn", unicorn.__version__, "python", sys.version.split()[0], "frozen", getattr(sys, "frozen", False), flush=True)
if mode in ("all", "main"):
    attempt("main-1M", 0x100000)
    attempt("main-128M", 0x08000000)
if mode in ("all", "thread"):
    in_thread("thread-1M", 0x100000)
    in_thread("thread-128M", 0x08000000)
    in_thread("thread-128M-nocpu", 0x08000000, cpu=False)
    in_thread("thread-128M-64Mstack", 0x08000000, stack=64 * 1024 * 1024)

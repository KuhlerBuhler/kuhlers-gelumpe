"""Run the device card probe against native FatFs and generated data, without an installed swap patch."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))
import sample_store_probe as probe
import swap_cases as c


class Link:
    def __init__(self, box):
        self.box = box

    def read(self, at, count):
        return bytes(self.box.m.uc.mem_read(at, count))

    def write_at(self, at, data):
        self.box.m.uc.mem_write(at, data)

    def execute(self, token):
        if self.box.dev.call(probe.STUB, token) != probe.MAGIC:
            raise ValueError('return marker differs')


def cases(vsb):
    samples = {500: ('Original generated sample', 100)}
    box = c.Box(vsb[256:], None, samples, [500])
    link = Link(box)
    probe.validate_device(link, vsb)
    report = probe.run(link, b'SD:/BT123ABC.all')
    folder = c.cardstore.card_folder(vsb[256:])
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    unchanged = volume.read(f'KORG/{folder}/Sample/e2sSample.all') == c.sampleset.build(samples)
    try:
        volume.stat('BT123ABC.all')
        removed = False
    except c.fat32.NotFound:
        removed = True
    volume.close()
    return [dict(id='card_probe_preserves_the_active_library_and_restores_its_ram',
                 ok=report['ok'] and report['ram_restored'] and unchanged and removed and not box.m.asserts,
                 active_library_unchanged=unchanged, test_file_removed=removed, probe=report)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vsb', required=True, type=Path)
    args = parser.parse_args()
    checks = cases(args.vsb.read_bytes())
    print(json.dumps(dict(hardware_contact=False, checks=checks), indent=2))
    return 0 if all(c['ok'] for c in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())

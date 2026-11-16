# The editor page and the emulator in one image, the same pair `npm start` runs.
# Node 20 or newer, Python 3.10 or newer with Unicorn (docs/development.md).
FROM node:22-bookworm-slim

# The page has to listen on every interface: a published port reaches the
# container's own address, never 127.0.0.1 inside it. The emulator takes the
# same variable.
ENV GELUMPE_HOST=0.0.0.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# The page is plain files, so no npm ci is needed. The emulator gets its own
# venv from the project's setup, the pinned Unicorn included.
# The runtime patches are built, not committed (tools/patch/ensure-runtime.mjs, AGENTS.md).
# They are built here, after the venv, so a container starts without writing into
# /app; data/patches belongs to node as well, because a rebuild after a source change
# writes its lock and the new file there.
RUN npm run setup:emu \
 && node tools/patch/ensure-runtime.mjs \
 && mkdir -p /home/node/.gelumpe /SD \
 && chown -R node:node /home/node/.gelumpe /SD tools/emu/.venv data/patches

# The card sits in /SD, a folder the host can open (docker-compose.yaml binds ./SD there);
# the flash stays under HOME.
ENV HOME=/home/node
ENV GELUMPE_SD_DIR=/SD
ENV GELUMPE_FLASH_DIR=/home/node/.gelumpe/flash
USER node

EXPOSE 8737 8740

# Healthy means the page answers. The emulator is not part of it: it starts only when a page powers the
# device on, and an editor nobody has opened yet is a container that works. No curl in this image, so
# Node does the request.
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:8737/').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

CMD ["node", "tools/start.mjs"]

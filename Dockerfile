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
RUN npm run setup:emu \
 && mkdir -p /home/node/.gelumpe /SD \
 && chown -R node:node /home/node/.gelumpe /SD tools/emu/.venv

# The card sits in /SD, a folder the host can open (docker-compose.yaml binds ./SD there);
# the flash stays under HOME.
ENV HOME=/home/node
ENV GELUMPE_SD_DIR=/SD
ENV GELUMPE_FLASH_DIR=/home/node/.gelumpe/flash
USER node

EXPOSE 8737 8740
CMD ["node", "tools/start.mjs"]

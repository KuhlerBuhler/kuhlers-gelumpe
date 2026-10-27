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
 && mkdir -p /home/node/.gelumpe \
 && mkdir SD
 && chown -R node:node /home/node/.gelumpe tools/emu/.venv

# The card and the flash land under HOME, which is the volume below.
ENV HOME=/home/node
USER node

EXPOSE 8737 8740
CMD ["node", "tools/start.mjs"]

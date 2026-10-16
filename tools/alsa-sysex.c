#define _POSIX_C_SOURCE 200809L
#include <alsa/asoundlib.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_MESSAGE (1024 * 1024)
#define EVENT_BYTES 256

static int alsa_error(const char *operation, int result) {
    fprintf(stderr, "%s: %s (%d)\n", operation, snd_strerror(result), result);
    return 1;
}

int main(int argc, char **argv) {
    unsigned client, port;
    char extra;
    if (argc != 3 || strcmp(argv[1], "--destination") != 0 ||
        sscanf(argv[2], "%u:%u%c", &client, &port, &extra) != 2 ||
        client > 255 || port > 255) {
        fprintf(stderr, "Usage: alsa-sysex --destination CLIENT:PORT < message.syx\n");
        return 1;
    }

    unsigned char *message = malloc(MAX_MESSAGE + 1);
    if (!message) return 1;
    size_t length = fread(message, 1, MAX_MESSAGE + 1, stdin);
    int valid = !ferror(stdin) && length >= 2 && length <= MAX_MESSAGE &&
                message[0] == 0xf0 && message[length - 1] == 0xf7;
    for (size_t i = 1; valid && i + 1 < length; i++) valid = message[i] < 0x80;
    if (!valid) {
        fprintf(stderr, "Expected one complete 7-bit SysEx frame, at most 1 MiB\n");
        free(message);
        return 1;
    }

    snd_seq_t *seq = NULL;
    snd_midi_event_t *encoder = NULL;
    snd_seq_port_info_t *destination = NULL;
    int exit_code = 1;
    int result = snd_seq_open(&seq, "default", SND_SEQ_OPEN_OUTPUT, SND_SEQ_NONBLOCK);
    if (result < 0) {
        alsa_error("open sequencer", result);
        free(message);
        return 1;
    }
    result = snd_seq_set_client_name(seq, "paced-sysex");
    if (result < 0) { alsa_error("name client", result); goto done; }
    result = snd_seq_port_info_malloc(&destination);
    if (result < 0) { alsa_error("allocate port info", result); goto done; }
    result = snd_seq_get_any_port_info(seq, client, port, destination);
    if (result < 0) { alsa_error("lookup destination", result); goto done; }
    if (!(snd_seq_port_info_get_capability(destination) & SND_SEQ_PORT_CAP_WRITE)) {
        fprintf(stderr, "Destination does not accept MIDI output\n");
        goto done;
    }
    int source = snd_seq_create_simple_port(seq, "output",
        SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_SUBS_READ,
        SND_SEQ_PORT_TYPE_MIDI_GENERIC | SND_SEQ_PORT_TYPE_APPLICATION);
    if (source < 0) { alsa_error("create source port", source); goto done; }
    result = snd_seq_connect_to(seq, source, client, port);
    if (result < 0) { alsa_error("connect destination", result); goto done; }
    result = snd_midi_event_new(EVENT_BYTES, &encoder);
    if (result < 0) { alsa_error("create encoder", result); goto done; }

    for (size_t offset = 0; offset < length;) {
        snd_seq_event_t event;
        snd_seq_ev_clear(&event);
        long consumed = snd_midi_event_encode(encoder, message + offset,
                                             (long)(length - offset), &event);
        if (consumed <= 0 || event.type != SND_SEQ_EVENT_SYSEX) {
            fprintf(stderr, "SysEx encoder did not produce an event\n");
            goto done;
        }
        snd_seq_ev_set_source(&event, source);
        snd_seq_ev_set_dest(&event, client, port);
        snd_seq_ev_set_direct(&event);
        result = snd_seq_event_output(seq, &event);
        if (result < 0) { alsa_error("output event", result); goto done; }
        result = snd_seq_drain_output(seq);
        if (result < 0) { alsa_error("drain output", result); goto done; }
        offset += (size_t)consumed;
        struct timespec remaining = {.tv_sec = 0, .tv_nsec = 2000000};
        while (nanosleep(&remaining, &remaining) < 0) {
            if (errno != EINTR) { perror("pace output"); goto done; }
        }
    }
    exit_code = 0;

done:
    if (destination) snd_seq_port_info_free(destination);
    if (encoder) snd_midi_event_free(encoder);
    snd_seq_close(seq);
    free(message);
    return exit_code;
}

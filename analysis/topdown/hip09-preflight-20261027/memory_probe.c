#include <stdint.h>
#include <stdlib.h>
#include <time.h>

/* Short PMU diagnostic only; unrelated to the document workloads. */
int main(void) {
    const size_t count = 1u << 23;
    volatile uint64_t *data = calloc(count, sizeof(*data));
    if (!data) return 1;
    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);
    uint64_t state = 1;
    do {
        for (unsigned i = 0; i < 65536; ++i) {
            state = state * 6364136223846793005ULL + 1;
            size_t index = (state >> 16) & (count - 1);
            data[index] = data[(index + 4096) & (count - 1)] + state;
        }
        clock_gettime(CLOCK_MONOTONIC, &now);
    } while ((now.tv_sec - start.tv_sec) + (now.tv_nsec - start.tv_nsec) / 1e9 < 3.0);
    free((void *)data);
    return 0;
}

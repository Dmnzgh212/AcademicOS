/* LifeHub glue; narrow JSON array of printable ASCII labels, no ambient imports. */
#include "vendor/strnatcmp.h"
__attribute__((import_module("lifehub_service"), import_name("read_request")))
extern int read_request(char *, int);
__attribute__((import_module("lifehub_service"), import_name("write_response")))
extern int write_response(char *, int);
#define ITEMS 32
#define LABEL 128
#define BYTES 8192
static char input[BYTES], output[BYTES], labels[ITEMS][LABEL + 1];
static int starts[ITEMS], ends[ITEMS], order[ITEMS];
static int ws(char c) { return c == ' ' || c == '\n' || c == '\r' || c == '\t'; }
__attribute__((export_name("run"))) int run(void) {
    int n = read_request(input, BYTES), p = 0, count = 0;
    if (n < 0 || n > BYTES) return 1;
    while (p < n && ws(input[p])) p++;
    if (p >= n || input[p++] != '[') return 1;
    while (p < n && ws(input[p])) p++;
    if (p < n && input[p] != ']') {
        for (;;) {
            if (count == ITEMS || p >= n || input[p] != '"') return 1;
            starts[count] = p++;
            int length = 0;
            while (p < n && input[p] != '"') {
                unsigned char c = input[p++];
                if (c == '\\') {
                    if (p >= n) return 1;
                    c = input[p++];
                    if (c != '"' && c != '\\' && c != '/') return 1;
                }
                if (c < 32 || c > 126 || length == LABEL) return 1;
                labels[count][length++] = c;
            }
            if (p >= n || input[p++] != '"') return 1;
            labels[count][length] = 0;
            ends[count] = p;
            order[count] = count;
            count++;
            while (p < n && ws(input[p])) p++;
            if (p < n && input[p] == ',') {
                p++;
                while (p < n && ws(input[p])) p++;
                continue;
            }
            break;
        }
    }
    if (p >= n || input[p++] != ']') return 1;
    while (p < n && ws(input[p])) p++;
    if (p != n) return 1;
    /* Stable insertion sort; preserve exact original escaped JSON strings. */
    for (int i = 1; i < count; i++) {
        int key = order[i], j = i;
        while (j > 0 && strnatcmp(labels[order[j-1]], labels[key]) > 0) {
            order[j] = order[j-1]; j--;
        }
        order[j] = key;
    }
    int used = 0;
    output[used++] = '[';
    for (int i = 0; i < count; i++) {
        if (i) output[used++] = ',';
        for (int k = starts[order[i]]; k < ends[order[i]]; k++) {
            if (used >= BYTES - 1) return 1;
            output[used++] = input[k];
        }
    }
    output[used++] = ']';
    return write_response(output, used) == used ? 0 : 1;
}

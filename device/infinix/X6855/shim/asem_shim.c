/*
 * ASEM Recovery - compatibility shim (X6855), preloaded (LD_PRELOAD) into the stock
 * Android 16 services that run inside the android-14.1 based recovery:
 *   - MediaTek boot control HAL (A/B slot switching)      - all builds
 *   - Trustonic TEE / KeyMint / Gatekeeper (decryption)   - ASEM_DECRYPT builds
 *
 * Symbol check (2026-10-16, every symbol those services need vs. what the recovery
 * libraries export) found exactly three missing - all provided here:
 *   AIBinder_Class_setTransactionCodeToFunctionNameMap   libbinder_ndk (newer API):
 *       only attaches debug names to transaction codes -> no-op
 *   std::__1::__libcpp_verbose_abort(const char*, ...)   libc++ (newer LLVM):
 *       log the message, abort() - same behaviour as the real one
 *   android::base::Join<std::vector<std::string>&, const char*>   libbase (newer
 *       template instantiation): joins strings with a separator
 *
 * Plain C on purpose: no NDK C++ code (the NDK's libc++ is std::__ndk1, the recovery's
 * is std::__1). Join builds its std::__1::string result ONLY through functions the
 * recovery's own libc++.so exports (append), treating strings as opaque 24-byte
 * objects; the vector is read as libc++'s {begin, end, cap} with 24-byte elements.
 *
 * Build (Android NDK r26, on the PC), linked against the recovery's own libc++.so:
 *   clang --target=aarch64-linux-android31 -shared -fPIC -O2 -Wall -Werror \
 *         -Wl,-soname,libasem_shim.so -o libasem_shim.so asem_shim.c \
 *         <recovery>/system/lib64/libc++.so -llog
 */
#include <android/log.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define EXPORT __attribute__((visibility("default")))

EXPORT void AIBinder_Class_setTransactionCodeToFunctionNameMap(void* clazz, const char** names, size_t count) {
    (void)clazz;
    (void)names;
    (void)count;
}

EXPORT __attribute__((noreturn))
void asem_libcpp_verbose_abort(const char* fmt, ...) __asm__("_ZNSt3__122__libcpp_verbose_abortEPKcz");

void asem_libcpp_verbose_abort(const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    __android_log_vprint(ANDROID_LOG_FATAL, "libc++", fmt, ap);
    va_end(ap);
    abort();
}

/* std::__1::string as an opaque object (sizeof == 24 on arm64; all-zero = empty). */
typedef struct { unsigned char bytes[24]; } asem_string;

/* exported by the recovery's libc++.so (checked): string& append(const char*) and
   string& append(const string& str, size_t pos, size_t n) */
extern void* asem_str_append_cstr(void* self, const char* s)
        __asm__("_ZNSt3__112basic_stringIcNS_11char_traitsIcEENS_9allocatorIcEEE6appendEPKc");
extern void* asem_str_append_str(void* self, const void* str, size_t pos, size_t n)
        __asm__("_ZNSt3__112basic_stringIcNS_11char_traitsIcEENS_9allocatorIcEEE6appendERKS5_mm");

/* std::string android::base::Join(std::vector<std::string>& things, const char* separator)
   AArch64: the 24-byte result comes back through x8 exactly like the C++ original. */
EXPORT asem_string asem_base_join(void* things, const char* separator) __asm__(
        "_ZN7android4base4JoinIRNSt3__16vectorINS2_12basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEENS7_IS9_EEEEPKcEES9_OT_T0_");

asem_string asem_base_join(void* things, const char* separator) {
    asem_string out;
    memset(&out, 0, sizeof(out));
    unsigned char* const* v = (unsigned char* const*)things;  /* {begin, end, end_of_storage} */
    for (unsigned char* p = v[0]; p < v[1]; p += sizeof(asem_string)) {
        if (p != v[0] && separator) asem_str_append_cstr(&out, separator);
        asem_str_append_str(&out, p, 0, (size_t)-1);
    }
    return out;
}

/*
 * ASEM Recovery - decryption shim (X6855).
 *
 * The stock Android 16 vendor TEE / KeyMint / Gatekeeper services run in the
 * android-14.1 based recovery. Of ~41,000 symbols they need, exactly two are missing
 * from the recovery's own libraries (checked with symcheck, 2026-10-16):
 *
 *   AIBinder_Class_setTransactionCodeToFunctionNameMap   (libbinder_ndk, newer API)
 *   std::__1::__libcpp_verbose_abort(const char*, ...)    (libc++, newer LLVM)
 *
 * This library provides both and is LD_PRELOADed only into those services.
 * Build (Android NDK r26, on the PC):
 *   clang --target=aarch64-linux-android31 -shared -fPIC -O2 -Wall -Werror \
 *         -Wl,-soname,libasem_shim.so -o libasem_shim.so asem_shim.c -llog
 */
#include <stdarg.h>
#include <stddef.h>
#include <stdlib.h>
#include <android/log.h>

/* libbinder_ndk: only attaches debug names to transaction codes - a no-op is correct. */
__attribute__((visibility("default")))
void AIBinder_Class_setTransactionCodeToFunctionNameMap(void* clazz, const char** names, size_t count) {
    (void)clazz;
    (void)names;
    (void)count;
}

/* libc++: report the message, then abort - same behaviour as the real one. */
__attribute__((noreturn, visibility("default")))
void asem_libcpp_verbose_abort(const char* fmt, ...) __asm__("_ZNSt3__122__libcpp_verbose_abortEPKcz");

void asem_libcpp_verbose_abort(const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    __android_log_vprint(ANDROID_LOG_FATAL, "libc++", fmt, ap);
    va_end(ap);
    abort();
}

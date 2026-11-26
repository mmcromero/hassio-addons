#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define TMPFS_BYTES (1024UL * 1024UL)
#define WRITE_TEST_BYTES (2UL * 1024UL * 1024UL)
#define WRITE_CHUNK (64UL * 1024UL)
#define SCRATCH_PREFIX "/tmp/fr-userns-probe-"

struct probe_report {
    bool user_namespace_created, uid_map_written, gid_map_written;
    bool mount_namespace_created, mount_propagation_private;
    bool net_namespace_created, pid_namespace_created, pid_namespace_init_verified;
    bool tmpfs_mounted, tmpfs_mode_verified, tmpfs_flags_verified, tmpfs_quota_enforced;
    bool tmpfs_unmount_ok, mountpoint_restored;
    unsigned int tmpfs_mode;
    unsigned long tmpfs_flags;
    unsigned long long tmpfs_size_bytes, tmpfs_written_before_enospc;
    char user_namespace_error[32], id_map_error[32], mount_namespace_error[32];
    char tmpfs_mount_error[32], tmpfs_size_error[32], tmpfs_mode_error[32], tmpfs_flags_error[32];
    char tmpfs_write_error[32], tmpfs_unmount_error[32];
    char mountpoint_restore_error[32], net_namespace_error[32], pid_namespace_error[32];
    char security_cap_eff[32], security_no_new_privs[8], security_seccomp[8];
    bool security_cap_sys_admin_in_userns;
    char security_apparmor[160];
};

static const char *errno_name(int e) {
    switch (e) {
        case EPERM: return "EPERM";
        case EACCES: return "EACCES";
        case EINVAL: return "EINVAL";
        case ENOSPC: return "ENOSPC";
        case EBUSY: return "EBUSY";
        case ENOENT: return "ENOENT";
        case EOPNOTSUPP: return "EOPNOTSUPP";
        case EUSERS: return "EUSERS";
        case ENOMEM: return "ENOMEM";
        case EIO: return "EIO";
        case EAGAIN: return "EAGAIN";
        default: return "OS_ERROR";
    }
}

static void copy_field(char *dst, size_t size, const char *src) {
    if (size) snprintf(dst, size, "%s", src ? src : "");
}

static int write_text_file(const char *path, const char *value) {
    int fd = open(path, O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return -1;
    size_t length = strlen(value), offset = 0;
    while (offset < length) {
        ssize_t n = write(fd, value + offset, length - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) {
            int saved = n < 0 ? errno : EIO;
            close(fd);
            errno = saved;
            return -1;
        }
        offset += (size_t)n;
    }
    if (close(fd) != 0) return -1;
    return 0;
}

static void read_security_context(struct probe_report *r) {
    FILE *f = fopen("/proc/self/status", "r");
    if (f) {
        char *line = NULL;
        size_t cap = 0;
        while (getline(&line, &cap, f) >= 0) {
            char *value = strchr(line, ':');
            if (!value) continue;
            *value++ = '\0';
            while (*value == ' ' || *value == '\t') value++;
            value[strcspn(value, "\r\n\t ")] = '\0';
            if (strcmp(line, "CapEff") == 0) {
                copy_field(r->security_cap_eff, sizeof(r->security_cap_eff), value);
                char *end = NULL;
                unsigned long long mask = strtoull(value, &end, 16);
                r->security_cap_sys_admin_in_userns = end != value && *end == '\0' && (mask & (1ULL << 21)) != 0;
            }
            else if (strcmp(line, "NoNewPrivs") == 0) copy_field(r->security_no_new_privs, sizeof(r->security_no_new_privs), value);
            else if (strcmp(line, "Seccomp") == 0) copy_field(r->security_seccomp, sizeof(r->security_seccomp), value);
        }
        free(line);
        fclose(f);
    }
    f = fopen("/proc/self/attr/current", "r");
    if (f) {
        if (fgets(r->security_apparmor, sizeof(r->security_apparmor), f))
            r->security_apparmor[strcspn(r->security_apparmor, "\r\n")] = '\0';
        fclose(f);
    }
}

static bool valid_scratch(const char *path) {
    if (strncmp(path, SCRATCH_PREFIX, strlen(SCRATCH_PREFIX)) != 0) return false;
    if (strchr(path + strlen(SCRATCH_PREFIX), '/')) return false;
    struct stat st;
    if (lstat(path, &st) != 0) return false;
    return S_ISDIR(st.st_mode) && !S_ISLNK(st.st_mode) && st.st_uid == geteuid() &&
           (st.st_mode & 07777) == 0700;
}

static void print_error_field(bool *first, const char *name, const char *value) {
    if (!value[0]) return;
    printf("%s\"%s\":\"%s\"", *first ? "" : ",", name, value);
    *first = false;
}

static bool mountinfo_is_private(void) {
    FILE *stream = fopen("/proc/self/mountinfo", "r");
    if (stream == NULL) return false;
    char *line = NULL;
    size_t capacity = 0;
    ssize_t length;
    bool saw_mount = false;
    bool found_root = false;
    bool private_tree = true;

    while ((length = getline(&line, &capacity, stream)) >= 0) {
        (void)length;
        char *separator = strstr(line, " - ");
        if (separator == NULL) {
            private_tree = false;
            break;
        }
        *separator = '\0';
        char *save = NULL;
        char *token = strtok_r(line, " ", &save);
        unsigned int field = 0;
        char *mountpoint = NULL;
        while (token != NULL) {
            if (field == 4) mountpoint = token;
            if (field >= 6 &&
                (strncmp(token, "shared:", 7) == 0 ||
                 strncmp(token, "master:", 7) == 0 ||
                 strncmp(token, "propagate_from:", 15) == 0 ||
                 strcmp(token, "unbindable") == 0)) {
                private_tree = false;
            }
            ++field;
            token = strtok_r(NULL, " ", &save);
        }
        if (mountpoint != NULL && strcmp(mountpoint, "/") == 0)
            found_root = true;
        saw_mount = true;
        if (!private_tree) break;
    }
    if (ferror(stream)) private_tree = false;
    free(line);
    if (fclose(stream) != 0) private_tree = false;
    return private_tree && saw_mount && found_root;
}

static void write_report(const struct probe_report *r) {
    printf("{\"user_namespace_created\":%s,\"uid_map_written\":%s,\"gid_map_written\":%s,"
           "\"mount_namespace_created\":%s,\"mount_propagation_private\":%s,"
           "\"net_namespace_created\":%s,\"pid_namespace_created\":%s,"
           "\"pid_namespace_init_verified\":%s,\"tmpfs_mounted\":%s,"
           "\"tmpfs_mode_verified\":%s,\"tmpfs_mode\":%u,"
           "\"tmpfs_flags_verified\":%s,\"tmpfs_flags\":%lu,"
           "\"tmpfs_size_bytes\":%llu,\"tmpfs_quota_enforced\":%s,"
           "\"tmpfs_written_before_enospc\":%llu,\"tmpfs_unmount_ok\":%s,"
           "\"mountpoint_restored\":%s,\"child_security_context\":{\"cap_eff\":\"%s\",\"cap_sys_admin_in_userns\":%s,\"no_new_privs\":\"%s\","
           "\"seccomp_mode\":\"%s\",\"apparmor_profile\":\"%s\"},\"errors\":{",
           r->user_namespace_created ? "true" : "false", r->uid_map_written ? "true" : "false",
           r->gid_map_written ? "true" : "false", r->mount_namespace_created ? "true" : "false",
           r->mount_propagation_private ? "true" : "false", r->net_namespace_created ? "true" : "false",
           r->pid_namespace_created ? "true" : "false", r->pid_namespace_init_verified ? "true" : "false",
           r->tmpfs_mounted ? "true" : "false", r->tmpfs_mode_verified ? "true" : "false",
           r->tmpfs_mode, r->tmpfs_flags_verified ? "true" : "false",
           r->tmpfs_flags, r->tmpfs_size_bytes, r->tmpfs_quota_enforced ? "true" : "false",
           r->tmpfs_written_before_enospc, r->tmpfs_unmount_ok ? "true" : "false",
           r->mountpoint_restored ? "true" : "false", r->security_cap_eff,
           r->security_cap_sys_admin_in_userns ? "true" : "false", r->security_no_new_privs,
           r->security_seccomp, r->security_apparmor);
    bool first = true;
    print_error_field(&first, "user_namespace", r->user_namespace_error);
    print_error_field(&first, "id_map", r->id_map_error);
    print_error_field(&first, "mount_namespace", r->mount_namespace_error);
    print_error_field(&first, "tmpfs_mount", r->tmpfs_mount_error);
    print_error_field(&first, "tmpfs_size", r->tmpfs_size_error);
    print_error_field(&first, "tmpfs_mode", r->tmpfs_mode_error);
    print_error_field(&first, "tmpfs_flags", r->tmpfs_flags_error);
    print_error_field(&first, "tmpfs_write", r->tmpfs_write_error);
    print_error_field(&first, "tmpfs_unmount", r->tmpfs_unmount_error);
    print_error_field(&first, "mountpoint_restore", r->mountpoint_restore_error);
    print_error_field(&first, "net_namespace", r->net_namespace_error);
    print_error_field(&first, "pid_namespace", r->pid_namespace_error);
    puts("}}");
}

int main(int argc, char **argv) {
    struct probe_report r = {0};
    bool mounted = false;
    struct stat scratch_initial = {0};
    bool scratch_initial_valid = false;
    if (argc != 2 || !valid_scratch(argv[1])) {
        copy_field(r.user_namespace_error, sizeof(r.user_namespace_error), "INVALID_SCRATCH");
        write_report(&r);
        return 0;
    }
    if (stat(argv[1], &scratch_initial) != 0 || !S_ISDIR(scratch_initial.st_mode)) {
        copy_field(r.user_namespace_error, sizeof(r.user_namespace_error), "SCRATCH_STAT_FAILED");
        write_report(&r);
        return 0;
    }
    scratch_initial_valid = true;

    /* AppArmor cx has already transitioned on exec. Prevent any later exec
       from gaining privilege before performing the synthetic namespace probe. */
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        copy_field(r.user_namespace_error, sizeof(r.user_namespace_error), errno_name(errno));
        write_report(&r);
        return 0;
    }

    read_security_context(&r);

    uid_t outer_uid = getuid();
    gid_t outer_gid = getgid();
    if (unshare(CLONE_NEWUSER) != 0) {
        copy_field(r.user_namespace_error, sizeof(r.user_namespace_error), errno_name(errno));
        write_report(&r);
        return 0;
    }
    r.user_namespace_created = true;

    char map[96];
    if (write_text_file("/proc/self/setgroups", "deny") != 0) {
        copy_field(r.id_map_error, sizeof(r.id_map_error), errno_name(errno));
        write_report(&r);
        return 0;
    }
    snprintf(map, sizeof(map), "0 %u 1", (unsigned)outer_uid);
    if (write_text_file("/proc/self/uid_map", map) != 0) {
        copy_field(r.id_map_error, sizeof(r.id_map_error), errno_name(errno));
        write_report(&r);
        return 0;
    }
    r.uid_map_written = true;
    snprintf(map, sizeof(map), "0 %u 1", (unsigned)outer_gid);
    if (write_text_file("/proc/self/gid_map", map) != 0) {
        copy_field(r.id_map_error, sizeof(r.id_map_error), errno_name(errno));
        write_report(&r);
        return 0;
    }
    r.gid_map_written = true;
    read_security_context(&r);

    if (unshare(CLONE_NEWNS) != 0) {
        copy_field(r.mount_namespace_error, sizeof(r.mount_namespace_error), errno_name(errno));
    } else {
        r.mount_namespace_created = true;
        if (mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) != 0) {
            copy_field(r.mount_namespace_error, sizeof(r.mount_namespace_error), errno_name(errno));
        } else if (!mountinfo_is_private()) {
            copy_field(r.mount_namespace_error, sizeof(r.mount_namespace_error),
                       "PROPAGATION_READBACK_FAILED");
        } else {
            r.mount_propagation_private = true;
            if (mount("tmpfs", argv[1], "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC,
                      "size=1048576,mode=0700") != 0) {
                copy_field(r.tmpfs_mount_error, sizeof(r.tmpfs_mount_error), errno_name(errno));
            } else {
                mounted = true;
                r.tmpfs_mounted = true;
                struct stat mounted_stat;
                if (stat(argv[1], &mounted_stat) != 0) {
                    copy_field(r.tmpfs_mode_error, sizeof(r.tmpfs_mode_error), errno_name(errno));
                } else {
                    r.tmpfs_mode = (unsigned int)(mounted_stat.st_mode & 07777);
                    r.tmpfs_mode_verified = S_ISDIR(mounted_stat.st_mode) && r.tmpfs_mode == 0700;
                    if (!r.tmpfs_mode_verified)
                        copy_field(r.tmpfs_mode_error, sizeof(r.tmpfs_mode_error), "MODE_NOT_0700");
                }
                struct statvfs st;
                if (statvfs(argv[1], &st) != 0) {
                    copy_field(r.tmpfs_size_error, sizeof(r.tmpfs_size_error), errno_name(errno));
                } else {
                    r.tmpfs_flags = (unsigned long)st.f_flag;
                    const unsigned long required_flags = ST_NOSUID | ST_NODEV | ST_NOEXEC;
                    r.tmpfs_flags_verified =
                        (r.tmpfs_flags & required_flags) == required_flags;
                    if (!r.tmpfs_flags_verified)
                        copy_field(r.tmpfs_flags_error, sizeof(r.tmpfs_flags_error),
                                   "REQUIRED_FLAGS_NOT_PRESENT");
                    r.tmpfs_size_bytes = (unsigned long long)st.f_blocks * (unsigned long long)st.f_frsize;
                    if (r.tmpfs_size_bytes == 0 || r.tmpfs_size_bytes > TMPFS_BYTES) {
                        copy_field(r.tmpfs_size_error, sizeof(r.tmpfs_size_error), "UNEXPECTED_CAPACITY");
                    } else {
                        char target[512];
                        snprintf(target, sizeof(target), "%s/quota-probe.bin", argv[1]);
                        int fd = open(target, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
                        if (fd < 0) {
                            copy_field(r.tmpfs_write_error, sizeof(r.tmpfs_write_error), errno_name(errno));
                        } else {
                            char chunk[WRITE_CHUNK];
                            memset(chunk, 'x', sizeof(chunk));
                            unsigned long long written = 0;
                            bool enospc = false;
                            while (written < WRITE_TEST_BYTES) {
                                size_t amount = (size_t)((WRITE_TEST_BYTES - written) < WRITE_CHUNK ?
                                                         (WRITE_TEST_BYTES - written) : WRITE_CHUNK);
                                ssize_t n = write(fd, chunk, amount);
                                if (n < 0 && errno == EINTR) continue;
                                if (n < 0 && errno == ENOSPC) { enospc = true; break; }
                                if (n <= 0) {
                                    copy_field(r.tmpfs_write_error, sizeof(r.tmpfs_write_error), errno_name(n < 0 ? errno : EIO));
                                    break;
                                }
                                written += (unsigned long long)n;
                            }
                            r.tmpfs_written_before_enospc = written;
                            if (close(fd) != 0 && !r.tmpfs_write_error[0])
                                copy_field(r.tmpfs_write_error, sizeof(r.tmpfs_write_error), errno_name(errno));
                            if (!enospc && !r.tmpfs_write_error[0])
                                copy_field(r.tmpfs_write_error, sizeof(r.tmpfs_write_error), "ENOSPC_NOT_OBSERVED");
                            r.tmpfs_quota_enforced = enospc && !r.tmpfs_write_error[0] &&
                                                     written >= TMPFS_BYTES * 3 / 4 &&
                                                     written <= TMPFS_BYTES + WRITE_CHUNK;
                        }
                    }
                }
            }
        }
    }

    if (mounted) {
        if (umount2(argv[1], MNT_DETACH) == 0) {
            r.tmpfs_unmount_ok = true;
            struct stat restored;
            if (scratch_initial_valid && lstat(argv[1], &restored) == 0 &&
                S_ISDIR(restored.st_mode) && restored.st_dev == scratch_initial.st_dev &&
                restored.st_ino == scratch_initial.st_ino) {
                r.mountpoint_restored = true;
            } else {
                copy_field(r.mountpoint_restore_error, sizeof(r.mountpoint_restore_error),
                           "SCRATCH_NOT_RESTORED");
            }
        } else {
            copy_field(r.tmpfs_unmount_error, sizeof(r.tmpfs_unmount_error), errno_name(errno));
        }
    }

    if (unshare(CLONE_NEWNET) == 0) r.net_namespace_created = true;
    else copy_field(r.net_namespace_error, sizeof(r.net_namespace_error), errno_name(errno));

    if (unshare(CLONE_NEWPID) == 0) {
        pid_t pid = fork();
        if (pid == 0) _exit(getpid() == 1 ? 0 : 91);
        if (pid < 0) copy_field(r.pid_namespace_error, sizeof(r.pid_namespace_error), errno_name(errno));
        else {
            int status = 0;
            if (waitpid(pid, &status, 0) < 0) copy_field(r.pid_namespace_error, sizeof(r.pid_namespace_error), errno_name(errno));
            else {
                r.pid_namespace_created = true;
                r.pid_namespace_init_verified = WIFEXITED(status) && WEXITSTATUS(status) == 0;
                if (!r.pid_namespace_init_verified)
                    copy_field(r.pid_namespace_error, sizeof(r.pid_namespace_error), "PID1_CHECK_FAILED");
            }
        }
    } else copy_field(r.pid_namespace_error, sizeof(r.pid_namespace_error), errno_name(errno));

    write_report(&r);
    return 0;
}

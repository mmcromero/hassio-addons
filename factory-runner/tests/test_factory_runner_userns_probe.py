import unittest

from userns_probe import summarize_status


class UserNamespaceProbeSummaryTests(unittest.TestCase):
    def test_user_namespace_only_is_partial_not_available(self):
        child = {
            "user_namespace_created": True,
            "uid_map_written": True,
            "gid_map_written": True,
        }
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True), "partial")

    def test_full_namespace_and_tmpfs_quota_contract_is_available(self):
        keys = (
            "user_namespace_created", "uid_map_written", "gid_map_written",
            "mount_namespace_created", "mount_propagation_private",
            "tmpfs_mounted", "tmpfs_quota_enforced", "tmpfs_unmount_ok",
            "net_namespace_created", "pid_namespace_created",
            "pid_namespace_init_verified",
        )
        child = {key: True for key in keys}
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True), "available")

    def test_missing_tmpfs_quota_is_partial(self):
        keys = (
            "user_namespace_created", "uid_map_written", "gid_map_written",
            "mount_namespace_created", "mount_propagation_private",
            "tmpfs_mounted", "tmpfs_unmount_ok", "net_namespace_created",
            "pid_namespace_created", "pid_namespace_init_verified",
        )
        child = {key: True for key in keys}
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True), "partial")

    def test_parent_mount_leak_or_capability_change_fails_closed(self):
        child = {"user_namespace_created": True}
        self.assertEqual(summarize_status(child, parent_mount_leaked=True,
                                          parent_capabilities_unchanged=True),
                         "failed_cleanup_or_parent_state")
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True,
                                          parent_sys_admin_before=True,
                                          parent_sys_admin_after=True),
                         "failed_cleanup_or_parent_state")
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=False),
                         "failed_cleanup_or_parent_state")

    def test_timeout_and_unavailable_userns(self):
        self.assertEqual(summarize_status({}, timed_out=True, parent_capabilities_unchanged=True), "timeout")
        self.assertEqual(summarize_status({}, parent_capabilities_unchanged=True), "blocked")


if __name__ == "__main__":
    unittest.main()

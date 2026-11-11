import unittest

from App.app_utils.navigation import (
    apply_requested_route,
    clear_sidebar_history,
    current_route,
    pop_route,
    push_route,
)


class NavigationTests(unittest.TestCase):
    def test_multi_step_return_path_preserves_origin(self):
        state = {"selected_page": "Overview", "jobs_current_page": 3}
        self.assertTrue(push_route(state, "Jobs", job_id=44))
        apply_requested_route(state)
        self.assertEqual(current_route(state), {"page": "Jobs", "job_id": 44})

        push_route(state, "Tailoring Studio", job_id=44)
        apply_requested_route(state)
        self.assertEqual(current_route(state), {"page": "Tailoring Studio", "job_id": None})

        pop_route(state)
        apply_requested_route(state)
        self.assertEqual(current_route(state), {"page": "Jobs", "job_id": 44})

        pop_route(state)
        apply_requested_route(state)
        self.assertEqual(current_route(state), {"page": "Overview", "job_id": None})
        self.assertEqual(state["jobs_current_page"], 3)

    def test_return_to_job_list_clears_selection_but_keeps_filters(self):
        state = {
            "selected_page": "Jobs", "jobs_current_page": 2,
            "jobs_search_filter": "network", "jobs_table_reset": 4,
        }
        push_route(state, "Jobs", job_id=44)
        apply_requested_route(state)
        pop_route(state)
        apply_requested_route(state)
        self.assertEqual(current_route(state), {"page": "Jobs", "job_id": None})
        self.assertEqual(state["jobs_current_page"], 2)
        self.assertEqual(state["jobs_search_filter"], "network")
        self.assertEqual(state["jobs_table_reset"], 5)

    def test_sidebar_navigation_starts_new_path(self):
        state = {
            "selected_page": "Applications", "active_job_detail": True,
            "navigation_history": [{"page": "Overview", "job_id": None}],
            "requested_route": {"page": "Jobs", "job_id": 44},
        }
        clear_sidebar_history(state)
        self.assertEqual(state["navigation_history"], [])
        self.assertFalse(state["active_job_detail"])
        self.assertNotIn("requested_route", state)

    def test_same_route_does_not_add_duplicate_history(self):
        state = {"selected_page": "Applications"}
        self.assertFalse(push_route(state, "Applications"))
        self.assertNotIn("navigation_history", state)


if __name__ == "__main__":
    unittest.main()

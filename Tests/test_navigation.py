import unittest

from App.app_utils.navigation import (
    apply_requested_route,
    clear_sidebar_history,
    current_route,
    pop_route,
    push_route,
    sidebar_navigate,
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

    def test_clicking_active_jobs_sidebar_item_returns_to_job_list(self):
        state = {
            "current_page": "Jobs", "active_job_detail": True,
            "selected_job_id": 44, "jobs_current_page": 2,
            "jobs_search_filter": "network", "jobs_table_reset": 4,
            "navigation_history": [{"page": "Jobs", "job_id": None}],
        }
        self.assertTrue(sidebar_navigate(state, "Jobs"))
        self.assertEqual(current_route(state), {"page": "Jobs", "job_id": None})
        self.assertEqual(state["navigation_history"], [])
        self.assertEqual(state["jobs_current_page"], 2)
        self.assertEqual(state["jobs_search_filter"], "network")
        self.assertEqual(state["jobs_table_reset"], 5)
        self.assertEqual(state["scroll_to_top"], 1)

    def test_sidebar_cross_page_navigation_and_same_page_click(self):
        state = {"current_page": "Jobs", "active_job_detail": True, "selected_job_id": 44}
        self.assertTrue(sidebar_navigate(state, "Applications"))
        self.assertEqual(current_route(state), {"page": "Applications", "job_id": None})
        self.assertFalse(sidebar_navigate(state, "Applications"))
        self.assertEqual(state["scroll_to_top"], 1)

    def test_back_from_tailoring_to_job_starts_at_top(self):
        state = {"current_page": "Jobs", "jobs_table_reset": 0}
        push_route(state, "Jobs", job_id=44)
        apply_requested_route(state)
        push_route(state, "Tailoring Studio", job_id=44)
        apply_requested_route(state)
        pop_route(state)
        apply_requested_route(state)
        self.assertEqual(current_route(state), {"page": "Jobs", "job_id": 44})
        self.assertEqual(state["scroll_to_top"], 3)


if __name__ == "__main__":
    unittest.main()

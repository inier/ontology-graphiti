import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.simulation.event_simulator.services.simulator_service import EventSimulatorService
from odap.biz.simulation.event_simulator.models.event import EventTemplate, GeneratedEvent, TimeControl


class TestCreateTemplate:
    @pytest.fixture
    def service(self):
        return EventSimulatorService()

    def test_create_template_basic(self, service):
        result = service.create_template(name="alert", event_type="alert")
        assert "template_id" in result
        assert result["name"] == "alert"
        assert result["event_type"] == "alert"

    def test_create_template_with_description(self, service):
        result = service.create_template(
            name="threat",
            event_type="threat",
            description="Threat detection event"
        )
        assert result["name"] == "threat"

    def test_create_template_with_schema(self, service):
        schema = {"severity": {"type": "string"}, "location": {"type": "object"}}
        result = service.create_template(
            name="geo_event",
            event_type="geo",
            schema=schema
        )
        assert result["template_id"] is not None

    def test_create_template_stored(self, service):
        result = service.create_template(name="stored", event_type="test")
        assert result["template_id"] in service._templates


class TestGenerateEvent:
    @pytest.fixture
    def service(self):
        svc = EventSimulatorService()
        svc.create_template(name="test_tpl", event_type="test")
        return svc

    def test_generate_event_success(self, service):
        template_id = list(service._templates.keys())[0]
        result = service.generate_event(template_id, {"key": "value"})
        assert "event_id" in result
        assert result["template_id"] == template_id
        assert result["event_type"] == "test"
        assert "timestamp" in result

    def test_generate_event_no_data(self, service):
        template_id = list(service._templates.keys())[0]
        result = service.generate_event(template_id)
        assert "event_id" in result

    def test_generate_event_nonexistent_template(self, service):
        result = service.generate_event("nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_generate_event_appended(self, service):
        template_id = list(service._templates.keys())[0]
        service.generate_event(template_id)
        service.generate_event(template_id)
        assert len(service._events) == 2


class TestListTemplates:
    @pytest.fixture
    def service(self):
        svc = EventSimulatorService()
        svc.create_template(name="tpl1", event_type="type1")
        svc.create_template(name="tpl2", event_type="type2")
        return svc

    def test_list_templates(self, service):
        result = service.list_templates()
        assert len(result) == 2
        names = [t["name"] for t in result]
        assert "tpl1" in names
        assert "tpl2" in names

    def test_list_templates_empty(self):
        service = EventSimulatorService()
        result = service.list_templates()
        assert result == []


class TestListEvents:
    @pytest.fixture
    def service(self):
        svc = EventSimulatorService()
        tpl = svc.create_template(name="evt_tpl", event_type="evt")
        for _ in range(5):
            svc.generate_event(tpl["template_id"])
        return svc

    def test_list_events_default_limit(self, service):
        result = service.list_events()
        assert len(result) == 5

    def test_list_events_with_limit(self, service):
        result = service.list_events(limit=2)
        assert len(result) == 2

    def test_list_events_empty(self):
        service = EventSimulatorService()
        result = service.list_events()
        assert result == []


class TestTimeControl:
    @pytest.fixture
    def service(self):
        return EventSimulatorService()

    def test_set_time_control(self, service):
        result = service.set_time_control(speed=2.0, is_paused=True)
        assert result["simulation_speed"] == 2.0
        assert result["is_paused"] is True

    def test_set_time_control_defaults(self, service):
        result = service.set_time_control()
        assert result["simulation_speed"] == 1.0
        assert result["is_paused"] is False

    def test_get_time_control(self, service):
        result = service.get_time_control()
        assert "simulation_speed" in result
        assert "current_time" in result
        assert "is_paused" in result

    def test_advance_clock(self, service):
        before = service._time_control.current_time
        result = service.advance_clock(60)
        assert "current_time" in result
        assert result["advanced_by_seconds"] == 60
        after = service._time_control.current_time
        assert after > before

    def test_advance_clock_with_speed(self, service):
        service.set_time_control(speed=10.0)
        before = service._time_control.current_time
        service.advance_clock(10)
        after = service._time_control.current_time
        diff = (after - before).total_seconds()
        assert diff == pytest.approx(100.0, abs=1.0)


class TestTriggers:
    @pytest.fixture
    def service(self):
        return EventSimulatorService()

    def test_register_trigger(self, service):
        result = service.register_trigger(
            "trig1",
            condition={"type": "event_count", "threshold": 5},
            action={"type": "notify"}
        )
        assert result["trigger_id"] == "trig1"
        assert result["status"] == "registered"

    def test_time_trigger_fires(self, service):
        past_time = (service._time_control.current_time + timedelta(hours=1)).isoformat()
        service.register_trigger(
            "time_trig",
            condition={"type": "time", "target_time": past_time},
            action={"type": "notify"}
        )
        result = service.advance_clock(7200)
        assert "time_trig" in result["triggers_fired"]

    def test_event_count_trigger_fires(self, service):
        tpl = service.create_template(name="trig_tpl", event_type="trig")
        service.register_trigger(
            "count_trig",
            condition={"type": "event_count", "threshold": 3},
            action={"type": "notify"}
        )
        for _ in range(3):
            service.generate_event(tpl["template_id"])
        result = service.advance_clock(1)
        assert "count_trig" in result["triggers_fired"]

    def test_disabled_trigger_does_not_fire(self, service):
        past_time = (service._time_control.current_time + timedelta(hours=1)).isoformat()
        service.register_trigger(
            "disabled_trig",
            condition={"type": "time", "target_time": past_time},
            action={"type": "notify"}
        )
        service._triggers["disabled_trig"]["enabled"] = False
        result = service.advance_clock(7200)
        assert "disabled_trig" not in result["triggers_fired"]

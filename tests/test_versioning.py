"""Tests for the Version Manager."""

from agentic_cxo.memory.versioning import VersionManager
from agentic_cxo.models import ContentChunk


class TestVersionManager:
    def setup_method(self):
        self.vm = VersionManager()

    def test_register_new_version(self):
        chunks = [ContentChunk(content="Revenue is $5M.")]
        deprecated = self.vm.register(chunks, source="report.pdf", version="1.0")
        assert deprecated == []
        assert len(self.vm.get_active_chunks()) == 1

    def test_deprecate_old_version(self):
        v1_chunks = [ContentChunk(content="Revenue is $5M.")]
        self.vm.register(v1_chunks, source="report.pdf", version="1.0")

        v2_chunks = [ContentChunk(content="Revenue is $6M.")]
        deprecated = self.vm.register(v2_chunks, source="report.pdf", version="2.0")

        assert len(deprecated) == 1
        active = self.vm.get_active_chunks()
        assert len(active) == 1
        assert active[0].content == "Revenue is $6M."

    def test_filter_by_source(self):
        self.vm.register([ContentChunk(content="A")], source="a.pdf", version="1.0")
        self.vm.register([ContentChunk(content="B")], source="b.pdf", version="1.0")
        assert len(self.vm.get_active_chunks(source="a.pdf")) == 1
        assert len(self.vm.get_active_chunks(source="b.pdf")) == 1
        assert len(self.vm.get_active_chunks()) == 2

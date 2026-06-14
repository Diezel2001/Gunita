"""Tests for the markdown parser module."""
from pathlib import Path

from bfai.entities import ExtractedEntity
from bfai.parser import (
    ParsedNote,
    extract_tags,
    extract_title,
    extract_wiki_links,
    parse_frontmatter,
    parse_note,
    strip_frontmatter,
)


class TestParseFrontmatter:
    """Tests for the parse_frontmatter function."""

    def test_no_frontmatter(self):
        """Content without frontmatter should return empty dict."""
        content = "# Hello\n\nThis is a note."
        assert parse_frontmatter(content) == {}

    def test_empty_content(self):
        """Empty content should return empty dict."""
        assert parse_frontmatter("") == {}

    def test_basic_frontmatter(self):
        """Basic frontmatter should be parsed correctly."""
        content = "---\ntitle: My Note\ntags: test, python\n---\n# Hello"
        result = parse_frontmatter(content)
        assert result == {"title": "My Note", "tags": "test, python"}

    def test_frontmatter_without_body(self):
        """Frontmatter without trailing content should work."""
        content = "---\ntitle: Solo\n---"
        result = parse_frontmatter(content)
        assert result == {"title": "Solo"}

    def test_value_with_colon(self):
        """Values containing colons should capture everything after first colon."""
        content = "---\ntitle: Note: Part Two\n---\n# Body"
        result = parse_frontmatter(content)
        assert result == {"title": "Note: Part Two"}

    def test_multiline_values_not_supported(self):
        """Only simple key: value pairs are supported (no multiline)."""
        content = "---\nkey: value1\n  continued\n---\n# Body"
        result = parse_frontmatter(content)
        # "  continued" has no colon so it's skipped
        assert result == {"key": "value1"}

    def test_no_trailing_newline_after_frontmatter(self):
        """Frontmatter at end of content should still parse."""
        content = "---\ntitle: Test\n---"
        result = parse_frontmatter(content)
        assert result == {"title": "Test"}

    def test_frontmatter_not_at_start(self):
        """Frontmatter delimiters not at start should not be parsed."""
        content = "Some text\n---\ntitle: Test\n---\n# Body"
        result = parse_frontmatter(content)
        assert result == {}

    def test_empty_frontmatter(self):
        """Empty frontmatter (--- ---) should return empty dict."""
        content = "---\n---\n# Body"
        result = parse_frontmatter(content)
        assert result == {}


class TestExtractTitle:
    """Tests for the extract_title function."""

    def test_title_from_frontmatter(self):
        """Title should be extracted from frontmatter metadata."""
        body = "# Heading Title\n\nSome content."
        metadata = {"title": "Frontmatter Title"}
        assert extract_title(body, metadata=metadata) == "Frontmatter Title"

    def test_title_from_frontmatter_no_metadata_arg(self):
        """Without metadata arg, should still extract from # heading."""
        body = "# My Heading\n\nContent."
        assert extract_title(body) == "My Heading"

    def test_title_from_frontmatter_with_no_body_match(self):
        """Frontmatter title takes priority over missing heading."""
        body = "No heading here, just text."
        metadata = {"title": "From Frontmatter"}
        assert extract_title(body, metadata=metadata) == "From Frontmatter"

    def test_title_from_heading(self):
        """Title should be extracted from the first # heading."""
        body = "# Project Alpha\n\nDescription here."
        assert extract_title(body) == "Project Alpha"

    def test_title_from_heading_with_spaces(self):
        """Heading with extra spaces should be stripped."""
        body = "#    Spaced Heading   \n\nContent."
        assert extract_title(body) == "Spaced Heading"

    def test_title_from_second_heading(self):
        """Only the first heading should be used."""
        body = "# First\n\n## Second\n\n# Third"
        assert extract_title(body) == "First"

    def test_no_title_available(self):
        """Content with no title should return empty string."""
        body = "Just a paragraph without any headings."
        assert extract_title(body) == ""

    def test_empty_content(self):
        """Empty content should return empty string."""
        assert extract_title("") == ""

    def test_heading_without_space_after_hash(self):
        """#heading without space should not match."""
        body = "#not-a-heading\n\nContent."
        assert extract_title(body) == ""

    def test_metadata_title_empty_string(self):
        """Empty frontmatter title should fall through to heading."""
        body = "# Heading Title\n\nContent."
        metadata = {"title": ""}
        assert extract_title(body, metadata=metadata) == "Heading Title"


class TestExtractTags:
    """Tests for the extract_tags function."""

    def test_inline_tags_in_body(self):
        """Inline #tag patterns in body should be extracted."""
        body = "This is a #test note about #python programming."
        assert extract_tags(body) == ["python", "test"]

    def test_inline_tags_at_start_of_line(self):
        """Tag at the start of a line should be extracted."""
        body = "#python is great\nAnd #javascript too"
        assert extract_tags(body) == ["javascript", "python"]

    def test_tags_with_hyphens(self):
        """Tags with hyphens should be extracted."""
        body = "Working on #my-project and #high-priority-task."
        assert extract_tags(body) == ["high-priority-task", "my-project"]

    def test_tags_with_underscores(self):
        """Tags with underscores should be extracted."""
        body = "Using #my_tag and #another_one."
        assert extract_tags(body) == ["another_one", "my_tag"]

    def test_heading_not_confused_with_tag(self):
        """ATX headings (# Title) should NOT be treated as tags."""
        body = "# This is a heading\n\nAnd a #tag in the paragraph."
        assert extract_tags(body) == ["tag"]

    def test_no_tags_in_content(self):
        """Content without tags should return empty list."""
        body = "Just a plain paragraph without any tags."
        assert extract_tags(body) == []

    def test_empty_content(self):
        """Empty content should return empty list."""
        assert extract_tags("") == []

    def test_duplicate_tags_deduplicated(self):
        """Duplicate tags should appear only once."""
        body = "Using #python and loving #python every day."
        assert extract_tags(body) == ["python"]

    def test_frontmatter_tags_only(self):
        """Tags from frontmatter metadata only (no body tags)."""
        body = "Just some text without inline tags."
        metadata = {"tags": "python, test, robotics"}
        assert extract_tags(body, metadata=metadata) == ["python", "robotics", "test"]

    def test_frontmatter_tags_inline_combined(self):
        """Tags from both frontmatter and inline should be merged and deduped."""
        body = "Working on #python and #robotics projects."
        metadata = {"tags": "python, test"}
        assert extract_tags(body, metadata=metadata) == ["python", "robotics", "test"]

    def test_frontmatter_tags_with_spaces(self):
        """Frontmatter tags separated by spaces (not commas) should still work."""
        body = "Content here."
        metadata = {"tags": "python test robotics"}
        assert extract_tags(body, metadata=metadata) == ["python", "robotics", "test"]

    def test_frontmatter_tags_empty(self):
        """Empty frontmatter tags should not add any tags."""
        body = "Content with #tag."
        metadata = {"tags": ""}
        assert extract_tags(body, metadata=metadata) == ["tag"]

    def test_no_metadata_provided(self):
        """Without metadata, only inline tags should be extracted."""
        body = "Content with #tag."
        assert extract_tags(body) == ["tag"]

    def test_metadata_with_no_tags_key(self):
        """Metadata without 'tags' key should not add tags."""
        body = "Content with #tag."
        metadata = {"title": "Hello"}
        assert extract_tags(body, metadata=metadata) == ["tag"]

    def test_frontmatter_tags_sorted(self):
        """Result should be sorted alphabetically."""
        body = "Content."
        metadata = {"tags": "zeta, alpha, beta"}
        assert extract_tags(body, metadata=metadata) == ["alpha", "beta", "zeta"]

    def test_tag_at_end_of_line(self):
        """Tag at end of line should be extracted."""
        body = "This line ends with a #tag"
        assert extract_tags(body) == ["tag"]

    def test_multiple_inline_tags_sorted(self):
        """Multiple inline tags should be sorted."""
        body = "Tags: #zeta, #alpha, #beta"
        assert extract_tags(body) == ["alpha", "beta", "zeta"]

    def test_tag_with_numbers(self):
        """Tags containing numbers should be extracted."""
        body = "Version #v2 and #python3."
        assert extract_tags(body) == ["python3", "v2"]

    def test_tag_starting_with_underscore(self):
        """Tags starting with underscore should be extracted."""
        body = "Using #_private and #__dunder."
        assert extract_tags(body) == ["__dunder", "_private"]


class TestExtractWikiLinks:
    """Tests for the extract_wiki_links function."""

    def test_basic_wiki_link(self):
        """A basic [[Link]] should be extracted."""
        body = "Check out [[ESP32-S3]] for details."
        assert extract_wiki_links(body) == ["ESP32-S3"]

    def test_wiki_link_with_display_text(self):
        """[[Link|Display Text]] should extract the link target only."""
        body = "See [[ESP32-S3|ESP32 datasheet]] for specs."
        assert extract_wiki_links(body) == ["ESP32-S3"]

    def test_multiple_wiki_links(self):
        """Multiple [[links]] should all be extracted."""
        body = "See [[Project X]] and [[ESP32-S3]] for details."
        assert extract_wiki_links(body) == ["ESP32-S3", "Project X"]

    def test_no_wiki_links(self):
        """Content without wiki links should return empty list."""
        body = "Just a plain paragraph without any links."
        assert extract_wiki_links(body) == []

    def test_empty_content(self):
        """Empty content should return empty list."""
        assert extract_wiki_links("") == []

    def test_duplicate_wiki_links_deduplicated(self):
        """Duplicate wiki links should appear only once."""
        body = "Using [[ESP32]] and referencing [[ESP32]] again."
        assert extract_wiki_links(body) == ["ESP32"]

    def test_wiki_links_sorted(self):
        """Wiki links should be sorted alphabetically."""
        body = "See [[Zeta]], [[Alpha]], and [[Beta]]."
        assert extract_wiki_links(body) == ["Alpha", "Beta", "Zeta"]

    def test_wiki_link_with_spaces_in_target(self):
        """Wiki link target with spaces should be preserved."""
        body = "See [[My Project Page]] for info."
        assert extract_wiki_links(body) == ["My Project Page"]

    def test_wiki_link_at_start_of_line(self):
        """Wiki link at the start of a line should be extracted."""
        body = "[[ESP32]] is a microcontroller."
        assert extract_wiki_links(body) == ["ESP32"]

    def test_incomplete_bracket_not_matched(self):
        """Single brackets or unclosed [[ should not match."""
        body = "Just [a link] and [[unclosed"
        assert extract_wiki_links(body) == []

    def test_wiki_link_with_empty_display(self):
        """[[Link|]] with empty display text should extract the target."""
        body = "See [[ESP32|]]."
        assert extract_wiki_links(body) == ["ESP32"]

    def test_mixed_tags_and_wiki_links(self):
        """Tags and wiki links should not interfere with each other."""
        body = "The #esp32 project [[ESP32-S3]] is #robotics."
        assert extract_wiki_links(body) == ["ESP32-S3"]

    def test_wiki_link_target_with_hyphens(self):
        """Wiki link targets with hyphens should be preserved."""
        body = "See [[high-priority-task]]."
        assert extract_wiki_links(body) == ["high-priority-task"]

    def test_wiki_link_target_with_underscores(self):
        """Wiki link targets with underscores should be preserved."""
        body = "See [[my_project]]."
        assert extract_wiki_links(body) == ["my_project"]


class TestStripFrontmatter:
    """Tests for the strip_frontmatter function."""

    def test_strip_frontmatter_basic(self):
        """Frontmatter should be removed from content."""
        content = "---\ntitle: Test\n---\n# Body\n\nContent."
        result = strip_frontmatter(content)
        assert result == "# Body\n\nContent."

    def test_strip_frontmatter_no_frontmatter(self):
        """Content without frontmatter should be returned unchanged."""
        content = "# Just a heading\n\nAnd some text."
        assert strip_frontmatter(content) == content

    def test_strip_frontmatter_empty_body(self):
        """Frontmatter-only content should return empty string."""
        content = "---\ntitle: Only Frontmatter\n---"
        result = strip_frontmatter(content)
        assert result == ""

    def test_strip_frontmatter_not_at_start(self):
        """Delimiters not at start should not be stripped."""
        content = "text\n---\ntitle: Test\n---\nBody"
        result = strip_frontmatter(content)
        assert result == content


class TestParseNote:
    """Tests for the full parse_note function."""

    def test_parse_with_frontmatter_and_heading(self):
        """Full parse should extract all components correctly."""
        content = "---\ntitle: My Project\ntags: python, test\n---\n# My Project\n\nDescription here."
        result = parse_note(content)
        assert isinstance(result, ParsedNote)
        assert result.title == "My Project"
        assert result.body == "# My Project\n\nDescription here."
        assert result.metadata == {"title": "My Project", "tags": "python, test"}
        assert result.tags == ["python", "test"]
        assert result.wiki_links == []

    def test_parse_with_frontmatter_title_only(self):
        """Frontmatter title should be used when no body heading."""
        content = "---\ntitle: Custom Title\n---\n\nContent without heading."
        result = parse_note(content)
        assert result.title == "Custom Title"
        assert result.body == "\nContent without heading."
        assert result.tags == []
        assert result.wiki_links == []

    def test_parse_with_heading_only(self):
        """Heading should be used when no frontmatter title."""
        content = "# Heading Title\n\nContent."
        result = parse_note(content)
        assert result.title == "Heading Title"
        assert result.body == "# Heading Title\n\nContent."
        assert result.metadata == {}
        assert result.tags == []
        assert result.wiki_links == []

    def test_parse_no_title(self):
        """Content with no title should return empty string title."""
        content = "Just a paragraph."
        result = parse_note(content)
        assert result.title == ""
        assert result.body == content
        assert result.metadata == {}
        assert result.tags == []
        assert result.wiki_links == []

    def test_parse_empty_content(self):
        """Empty content should return empty defaults."""
        result = parse_note("")
        assert result.title == ""
        assert result.body == ""
        assert result.metadata == {}
        assert result.tags == []
        assert result.wiki_links == []

    def test_parse_frontmatter_with_metadata_only(self):
        """Frontmatter with no body heading uses filename or empty."""
        content = "---\ntags: robotics\n---\n\nSome content without a heading."
        result = parse_note(content)
        assert result.title == ""
        assert result.body == "\nSome content without a heading."
        assert result.metadata == {"tags": "robotics"}
        assert result.tags == ["robotics"]
        assert result.wiki_links == []

    def test_parse_heading_and_body_preserved(self):
        """The body should preserve original markdown structure."""
        content = "# Title\n\n## Section 1\n\nSome text.\n\n## Section 2\n\nMore text."
        result = parse_note(content)
        assert result.title == "Title"
        assert result.body == content
        assert result.tags == []
        assert result.wiki_links == []

    def test_parse_with_inline_tags(self):
        """Inline #tags in the body should be extracted."""
        content = "# My Note\n\nThis is a #robotics and #python project."
        result = parse_note(content)
        assert result.title == "My Note"
        assert result.tags == ["python", "robotics"]
        assert result.wiki_links == []

    def test_parse_with_frontmatter_and_inline_tags(self):
        """Frontmatter and inline tags should be merged."""
        content = "---\ntags: test, python\n---\n# My Note\n\nThis is a #robotics project."
        result = parse_note(content)
        assert result.tags == ["python", "robotics", "test"]
        assert result.wiki_links == []

    def test_parse_with_wiki_links(self):
        """Wiki links in the body should be extracted."""
        content = "# Project X\n\nUses [[ESP32-S3]] and references [[Project Y]]."
        result = parse_note(content)
        assert result.title == "Project X"
        assert result.wiki_links == ["ESP32-S3", "Project Y"]

    def test_parse_with_tags_and_wiki_links(self):
        """Tags and wiki links should both be extracted independently."""
        content = "---\ntags: robotics, esp32\n---\n# ESP32 Robot\n\nUses [[ESP32-S3]] and #robot project."
        result = parse_note(content)
        assert result.tags == ["esp32", "robot", "robotics"]
        assert result.wiki_links == ["ESP32-S3"]

    def test_parse_with_wiki_links_with_display_text(self):
        """Wiki links with display text should extract only the target."""
        content = "# Note\n\nSee [[ESP32-S3|ESP32 Datasheet]] for details."
        result = parse_note(content)
        assert result.wiki_links == ["ESP32-S3"]

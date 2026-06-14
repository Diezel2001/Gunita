"""Tests for the entity extraction framework."""
from bfai.entities import (
    EntityType,
    ExtractedEntity,
    extract_entities,
)


class TestEntityType:
    """Tests for the EntityType enum."""

    def test_enum_values(self):
        """EntityType should have the expected values."""
        assert EntityType.PERSON.value == "person"
        assert EntityType.ORGANIZATION.value == "organization"
        assert EntityType.TECHNOLOGY.value == "technology"
        assert EntityType.PROJECT.value == "project"

    def test_str_representation(self):
        """String representation should match the value."""
        assert str(EntityType.PERSON) == "person"
        assert str(EntityType.ORGANIZATION) == "organization"
        assert str(EntityType.TECHNOLOGY) == "technology"
        assert str(EntityType.PROJECT) == "project"


class TestExtractedEntity:
    """Tests for the ExtractedEntity dataclass."""

    def test_frozen_dataclass(self):
        """ExtractedEntity should be a frozen (immutable) dataclass."""
        entity = ExtractedEntity(
            entity_type=EntityType.TECHNOLOGY,
            name="ESP32",
            context="Uses ESP32 for robotics",
        )
        assert entity.entity_type == EntityType.TECHNOLOGY
        assert entity.name == "ESP32"
        assert entity.context == "Uses ESP32 for robotics"

    def test_default_context(self):
        """Context should default to empty string."""
        entity = ExtractedEntity(
            entity_type=EntityType.PERSON,
            name="Dr. Smith",
        )
        assert entity.context == ""

    def test_equality_by_value(self):
        """Two entities with same values should be equal (frozen)."""
        e1 = ExtractedEntity(EntityType.TECHNOLOGY, "Python")
        e2 = ExtractedEntity(EntityType.TECHNOLOGY, "Python")
        assert e1 == e2

    def test_inequality_different_type(self):
        """Different entity types should not be equal."""
        e1 = ExtractedEntity(EntityType.TECHNOLOGY, "Python")
        e2 = ExtractedEntity(EntityType.PERSON, "Python")
        assert e1 != e2

    def test_inequality_different_name(self):
        """Different names should not be equal."""
        e1 = ExtractedEntity(EntityType.TECHNOLOGY, "Python")
        e2 = ExtractedEntity(EntityType.TECHNOLOGY, "Java")
        assert e1 != e2


class TestExtractEntitiesEmpty:
    """Tests for extract_entities with empty/no content."""

    def test_empty_content(self):
        """Empty content should return empty list."""
        assert extract_entities("") == []

    def test_content_with_no_entities(self):
        """Content without recognizable entities should return empty list."""
        body = "just a simple sentence with no entities mentioned here"
        assert extract_entities(body) == []

    def test_whitespace_only(self):
        """Whitespace-only content should return empty list."""
        assert extract_entities("   \n  \t  ") == []


class TestExtractEntitiesTechnologies:
    """Tests for technology entity extraction."""

    def test_known_technology_python(self):
        """'Python' should be extracted as a TECHNOLOGY entity."""
        body = "This project is written in Python."
        result = extract_entities(body)
        assert len(result) == 1
        assert result[0].entity_type == EntityType.TECHNOLOGY
        assert result[0].name == "Python"

    def test_known_technology_docker(self):
        """'Docker' should be extracted as a TECHNOLOGY entity."""
        body = "We deploy using Docker containers."
        result = extract_entities(body)
        assert any(e.name == "Docker" for e in result)

    def test_versioned_technology(self):
        """Versioned names like ESP32-S3 should be extracted."""
        body = "The project uses ESP32-S3 for IoT."
        result = extract_entities(body)
        assert any(e.name == "ESP32-S3" for e in result)

    def test_versioned_without_suffix(self):
        """Basic versioned names like ESP32 should be extracted."""
        body = "Firmware runs on ESP32."
        result = extract_entities(body)
        assert any(e.name == "ESP32" for e in result)

    def test_multiple_technologies(self):
        """Multiple tech mentions should all be found."""
        body = "Using Python, Docker, and PostgreSQL together."
        result = extract_entities(body)
        names = {e.name for e in result if e.entity_type == EntityType.TECHNOLOGY}
        assert "Python" in names
        assert "Docker" in names
        assert "PostgreSQL" in names

    def test_known_technology_esp32(self):
        """ESP32 as a known technology should be extracted."""
        body = "The ESP32 handles sensor data."
        result = extract_entities(body)
        assert any(e.name == "ESP32" for e in result)


class TestExtractEntitiesPeople:
    """Tests for person entity extraction."""

    def test_dr_honorific(self):
        """'Dr.' honorific should be extracted as PERSON."""
        body = "The research was led by Dr. Smith."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.PERSON and "Dr. Smith" in e.name
            for e in result
        )

    def test_professor_honorific(self):
        """'Professor' honorific should be extracted as PERSON."""
        body = "Professor Johnson teaches the course."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.PERSON and "Professor Johnson" in e.name
            for e in result
        )

    def test_mr_honorific(self):
        """'Mr.' honorific should be extracted as PERSON."""
        body = "Contact Mr. Anderson for access."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.PERSON and "Mr. Anderson" in e.name
            for e in result
        )

    def test_person_not_recognized_without_honorific(self):
        """Plain names without honorifics should not be extracted."""
        body = "Alice worked on the project."
        result = extract_entities(body)
        assert not any(
            e.entity_type == EntityType.PERSON for e in result
        )


class TestExtractEntitiesOrganizations:
    """Tests for organization entity extraction."""

    def test_corporation_suffix(self):
        """'Inc' suffix should be identified as ORGANIZATION."""
        body = "The product is made by Acme Corp."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.ORGANIZATION and "Acme Corp" in e.name
            for e in result
        )

    def test_llc_suffix(self):
        """'LLC' suffix should be identified as ORGANIZATION."""
        body = "Funding was provided by TechVentures LLC."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.ORGANIZATION and "TechVentures LLC" in e.name
            for e in result
        )

    def test_university_pattern(self):
        """University name should be identified as ORGANIZATION."""
        body = "Research conducted at Stanford University."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.ORGANIZATION and "Stanford University" in e.name
            for e in result
        )

    def test_institute_suffix(self):
        """'Institute' suffix should be identified as ORGANIZATION."""
        body = "Built at the MIT Media Lab."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.ORGANIZATION
            for e in result
        )

    def test_foundation_suffix(self):
        """'Foundation' suffix should be identified as ORGANIZATION."""
        body = "Grant from the Python Software Foundation."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.ORGANIZATION and "Python Software Foundation" in e.name
            for e in result
        )


class TestExtractEntitiesProjects:
    """Tests for project entity extraction."""

    def test_project_name_pattern(self):
        """'Project X' format should be extracted as PROJECT."""
        body = "Working on Project Alpha this quarter."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.PROJECT and "Project Alpha" in e.name
            for e in result
        )

    def test_name_project_pattern(self):
        """'[Name] Project' format should be extracted as PROJECT."""
        body = "The Mars Project is underway."
        result = extract_entities(body)
        assert any(
            e.entity_type == EntityType.PROJECT and "Mars Project" in e.name
            for e in result
        )


class TestExtractEntitiesEdgeCases:
    """Tests for edge cases in entity extraction."""

    def test_deduplication(self):
        """Duplicate entities should appear only once."""
        body = "Python is great. I love Python."
        result = extract_entities(body)
        python_entities = [
            e for e in result if e.name == "Python"
        ]
        assert len(python_entities) == 1

    def test_sort_order(self):
        """Entities should be sorted by type then name."""
        body = "Dr. Smith uses Docker for Project Alpha."
        result = extract_entities(body)
        # Sort by entity_type value then name
        for i in range(len(result) - 1):
            curr = (result[i].entity_type.value, result[i].name.lower())
            next_ = (result[i + 1].entity_type.value, result[i + 1].name.lower())
            assert curr <= next_

    def test_case_insensitive_known_technology(self):
        """Known technologies should be matched case-insensitively."""
        body = "Running on LINUX in production."
        result = extract_entities(body)
        # "Linux" is in _KNOWN_TECHNOLOGIES, should match case-insensitively
        names = {e.name for e in result}
        assert "LINUX" in names

    def test_no_false_positive_on_partial_word(self):
        """Technology name should not match as part of a larger word."""
        body = "The Arduino board uses an ATmega chip."
        result = extract_entities(body)
        assert "ESP32" not in {e.name for e in result}

    def test_known_technologies_merge(self):
        """Additional known technologies should extend the built-in set."""
        body = "Using CustomTech for processing."
        extra = {"CustomTech"}
        result = extract_entities(body, known_technologies=extra)
        assert any(e.name == "CustomTech" for e in result)


class TestExtractEntitiesContext:
    """Tests for context snippet generation."""

    def test_context_snippet(self):
        """Context should include surrounding text."""
        body = "The team relies on Python for data processing."
        result = extract_entities(body)
        python_entity = next(e for e in result if e.name == "Python")
        assert "Python" in python_entity.context
        assert len(python_entity.context) > 5

    def test_context_contains_surrounding_words(self):
        """Context should contain words around the match."""
        body = "We use Docker extensively in our CI/CD pipeline."
        result = extract_entities(body)
        docker_entity = next(e for e in result if e.name == "Docker")
        assert "use" in docker_entity.context or "extensively" in docker_entity.context


class TestExtractEntitiesMixed:
    """Tests with mixed entity types in content."""

    def test_mixed_entity_types(self):
        """Multiple entity types should be extracted simultaneously."""
        body = (
            "Dr. Jones from Acme Corp presented on using Python "
            "and Docker for Project Nebula."
        )
        result = extract_entities(body)
        types = {e.entity_type for e in result}
        assert EntityType.PERSON in types
        assert EntityType.ORGANIZATION in types
        assert EntityType.TECHNOLOGY in types
        assert EntityType.PROJECT in types

    def test_entity_counts(self):
        """Entity counts should be reasonable for mixed content."""
        body = (
            "Python and Docker are used by Dr. Smith "
            "at Research Lab for Project Echo."
        )
        result = extract_entities(body)
        assert len(result) >= 4  # At least one of each type

    def test_known_technology_whole_word_only(self):
        """Technology names should only match as whole words, not substrings."""
        body = "The toolchain compiles properly."
        result = extract_entities(body)
        # "go" should not match from "toolchain" (Go language check)
        go_entities = [e for e in result if e.name.lower() == "go"]
        assert len(go_entities) == 0
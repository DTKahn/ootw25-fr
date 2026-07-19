import { describe, it, expect } from "vitest";
import { deriveSourceRows, derivePage, plainText } from "./seedSource";

describe("plainText", () => {
  it("strips HTML tags", () => {
    expect(plainText("Hello <strong>world</strong>")).toBe("Hello world");
  });

  it("decodes HTML entities", () => {
    expect(plainText("Space &amp; Science")).toBe("Space & Science");
  });

  it("collapses whitespace and trims", () => {
    expect(plainText("  Hello\n  world  ")).toBe("Hello world");
  });
});

describe("derivePage", () => {
  it("extracts the page slug before the first ' § '", () => {
    expect(derivePage("artemis-ii-mission § meta § title")).toBe("artemis-ii-mission");
  });

  it("returns the whole id when there is no separator", () => {
    expect(derivePage("no-separator")).toBe("no-separator");
  });
});

describe("deriveSourceRows", () => {
  it("maps catalog entries to source rows, using live French when present", () => {
    const entries = [
      {
        id: "artemis-ii-mission § meta § title",
        section: "meta",
        tag: "title",
        en: "Artemis II Mission &amp; Crew",
        fr: "Mission Artemis II <em>et</em> équipage",
        status: "translated",
      },
    ];
    const liveFrench = {
      "artemis-ii-mission § meta § title": "Mission Artemis II et l'équipage",
    };
    const result = deriveSourceRows(entries, liveFrench);
    expect(result).toEqual([
      {
        id: "artemis-ii-mission § meta § title",
        page: "artemis-ii-mission",
        english: "Artemis II Mission & Crew",
        liveFrench: "Mission Artemis II et l'équipage",
        suggestedFrench: "Mission Artemis II et équipage",
      },
    ]);
  });

  it("sets liveFrench to null when there is no matching key", () => {
    const entries = [
      { id: "x § y § z", section: "y", tag: "z", en: "E", fr: "F", status: "translated" },
    ];
    const result = deriveSourceRows(entries, {});
    expect(result[0].liveFrench).toBeNull();
  });
});

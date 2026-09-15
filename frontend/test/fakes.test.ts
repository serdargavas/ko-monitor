import { describe, expect, it } from "vitest";
import { installStreamFakes, restoreObjectUrlStubs } from "./fakes";

describe("installStreamFakes / restoreObjectUrlStubs", () => {
  it("restores URL.createObjectURL and revokeObjectURL to their pre-stub state", () => {
    const createBefore = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
    const revokeBefore = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");

    const { createObjectURL, revokeObjectURL } = installStreamFakes();
    expect(URL.createObjectURL).toBe(createObjectURL);
    expect(URL.revokeObjectURL).toBe(revokeObjectURL);

    restoreObjectUrlStubs();

    expect(Object.getOwnPropertyDescriptor(URL, "createObjectURL")).toEqual(createBefore);
    expect(Object.getOwnPropertyDescriptor(URL, "revokeObjectURL")).toEqual(revokeBefore);
  });

  it("is safe to call when nothing was installed", () => {
    expect(() => restoreObjectUrlStubs()).not.toThrow();
  });
});

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test, expect } from "@playwright/test";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import {
  applyAiSuggestion,
  blank,
  payload,
  validate,
  type Pet,
} from "../src/domain";

const samples = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "../docs/week9/sample-inputs.json"),
    "utf8",
  ),
) as {
  cases: Array<{
    id: string;
    context: { pets: Pet[] };
    output: { draft: unknown; questions: string[] };
  }>;
};
const schema = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "../docs/week9/ai-parse-schema.json"),
    "utf8",
  ),
);
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
const validateResponse = ajv.compile(schema);

for (const sample of samples.cases) {
  test(`映射 C 的 AI 示例 ${sample.id}`, () => {
    expect(
      validateResponse(sample.output),
      JSON.stringify(validateResponse.errors),
    ).toBe(true);
    const draft = blank();
    const warnings = applyAiSuggestion(
      draft,
      sample.output.draft,
      sample.context.pets,
    );
    expect(warnings).toEqual([]);
    expect(validate(draft, sample.context.pets)).toEqual([]);
    const request = payload(draft);
    expect(request.pet_ids).toEqual(sample.context.pets.map((pet) => pet.id));
    expect(request.window_start).toMatch(/(?:Z|[+-]\d{2}:\d{2})$/);
    expect(request.checklist_items.every((item) => item.content)).toBe(true);
    expect(sample.output.questions).toEqual([]);
  });
}

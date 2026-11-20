export type Kind = "home_visit" | "dog_walking" | "errand_buy";
export const kinds: Record<Kind, string> = {
  home_visit: "上门代看",
  dog_walking: "上门遛狗",
  errand_buy: "用品代买",
};
export interface Pet {
  id: string;
  name: string;
  species: "cat" | "dog";
  birth_date: string;
  breed?: string;
  temperament?: string;
  precautions?: string;
  supplies_location?: string;
  care_instructions?: string;
}
export interface Item {
  item_key: string;
  position: number;
  content: string;
  completion_condition: string;
  required: boolean;
  pet_id?: string | null;
  product_name?: string;
  quantity?: number;
  unit?: string;
}
export interface Draft {
  pet_ids: string[];
  service_type: Kind;
  fee_type: "" | "free" | "paid";
  window_start: string;
  window_end: string;
  expected_duration_minutes: number | null;
  location: string;
  budget: string;
  handover_notes: string;
  emergency_contact: string;
  requirements: string;
  precautions: string;
  raw_text: string;
  checklist_items: Item[];
}
export interface RequestRow extends Partial<Draft> {
  id: string;
  version: number;
  status: string;
  service_type: Kind;
}
export const blank = (): Draft => ({
  pet_ids: [],
  service_type: "home_visit",
  fee_type: "",
  window_start: "",
  window_end: "",
  expected_duration_minutes: null,
  location: "",
  budget: "0.00",
  handover_notes: "",
  emergency_contact: "",
  requirements: "",
  precautions: "",
  raw_text: "",
  checklist_items: [
    {
      item_key: "care_1",
      pet_id: null,
      position: 1,
      content: "",
      completion_condition: "",
      required: true,
    },
  ],
});
export function fixedItems(kind: Kind): Item[] {
  return (
    kind === "dog_walking"
      ? ["pickup", "departure", "return"]
      : kind === "errand_buy"
        ? ["purchase", "delivery"]
        : ["care_1"]
  ).map((key, i) => ({
    item_key: key,
    pet_id: null,
    position: i + 1,
    content:
      (
        {
          pickup: "接狗",
          departure: "出发",
          return: "送回",
          purchase: "购买指定商品",
          delivery: "交付核对",
        } as Record<string, string>
      )[key] || "",
    completion_condition: "",
    required: true,
  }));
}
export function beijing(value: string) {
  return /([zZ]|[+-]\d\d:\d\d)$/.test(value) ? value : value + ":00+08:00";
}
export function beijingInput(value: string) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("sv-SE", {
      timeZone: "Asia/Shanghai",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(date)
      .map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

type JsonObject = Record<string, unknown>;
function object(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function presentString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function applyAiSuggestion(
  target: Draft,
  suggestion: unknown,
  pets: Pet[],
) {
  const warnings: string[] = [];
  if (!object(suggestion)) return ["AI 草稿不是有效对象，未应用到表单"];

  const kind = suggestion.service_type;
  if (
    kind === "home_visit" ||
    kind === "dog_walking" ||
    kind === "errand_buy"
  ) {
    if (target.service_type !== kind) {
      target.service_type = kind;
      target.pet_ids = [];
      target.checklist_items = fixedItems(kind);
      target.budget = "";
    }
  } else {
    warnings.push("AI 未返回有效的服务类型");
  }

  if (Array.isArray(suggestion.pet_ids)) {
    const validIds = suggestion.pet_ids.filter(
      (id): id is string =>
        typeof id === "string" &&
        pets.some(
          (pet) =>
            pet.id === id &&
            (target.service_type !== "dog_walking" || pet.species === "dog"),
        ),
    );
    if (validIds.length !== suggestion.pet_ids.length)
      warnings.push("AI 返回了不存在或类型不符的宠物，已忽略");
    if (validIds.length) target.pet_ids = [...new Set(validIds)];
  }

  if (suggestion.fee_type === "free" || suggestion.fee_type === "paid")
    target.fee_type = suggestion.fee_type;
  for (const key of [
    "location",
    "handover_notes",
    "emergency_contact",
    "requirements",
    "precautions",
  ] as const) {
    if (presentString(suggestion[key])) target[key] = suggestion[key];
  }
  if (presentString(suggestion.window_start))
    target.window_start = beijingInput(suggestion.window_start);
  if (presentString(suggestion.window_end))
    target.window_end = beijingInput(suggestion.window_end);
  if (
    Number.isInteger(suggestion.expected_duration_minutes) &&
    Number(suggestion.expected_duration_minutes) > 0
  )
    target.expected_duration_minutes = Number(
      suggestion.expected_duration_minutes,
    );
  if (typeof suggestion.budget === "number" && suggestion.budget >= 0)
    target.budget = suggestion.budget.toFixed(2);

  if (Array.isArray(suggestion.checklist_items)) {
    const items: Item[] = [];
    for (const raw of suggestion.checklist_items) {
      if (
        !object(raw) ||
        !presentString(raw.item_key) ||
        !Number.isInteger(raw.position) ||
        Number(raw.position) < 1 ||
        !presentString(raw.content) ||
        !presentString(raw.completion_condition) ||
        typeof raw.required !== "boolean"
      ) {
        warnings.push("AI 清单包含格式不完整的项目，未覆盖当前清单");
        items.length = 0;
        break;
      }
      const petId = raw.pet_id;
      if (
        petId !== null &&
        petId !== undefined &&
        (typeof petId !== "string" || !target.pet_ids.includes(petId))
      ) {
        warnings.push("AI 清单指定了不属于本次需求的宠物，未覆盖当前清单");
        items.length = 0;
        break;
      }
      const item: Item = {
        item_key: raw.item_key,
        pet_id: petId === null ? null : (petId as string | undefined),
        position: Number(raw.position),
        content: raw.content,
        completion_condition: raw.completion_condition,
        required: raw.required,
      };
      if (presentString(raw.product_name)) item.product_name = raw.product_name;
      if (Number.isInteger(raw.quantity) && Number(raw.quantity) > 0)
        item.quantity = Number(raw.quantity);
      if (presentString(raw.unit)) item.unit = raw.unit;
      items.push(item);
    }
    const keys = items.map((item) => item.item_key);
    const requiredKeys =
      target.service_type === "dog_walking"
        ? ["pickup", "departure", "return"]
        : target.service_type === "errand_buy"
          ? ["purchase", "delivery"]
          : [];
    if (
      items.length &&
      (new Set(keys).size !== keys.length ||
        requiredKeys.some((key, index) => keys[index] !== key))
    ) {
      warnings.push("AI 清单缺少固定步骤或存在重复标识，未覆盖当前清单");
    } else if (items.length) {
      target.checklist_items = items.sort((a, b) => a.position - b.position);
    }
  }
  return warnings;
}
export function validate(d: Draft, pets: Pet[]): string[] {
  const e: string[] = [];
  if (!d.pet_ids.length) e.push("请选择至少一只宠物");
  if (
    d.pet_ids.some(
      (id) =>
        !pets.some(
          (p) =>
            p.id === id &&
            (d.service_type !== "dog_walking" || p.species === "dog"),
        ),
    )
  )
    e.push("所选宠物无效，遛狗只能选择犬类");
  const start = Date.parse(beijing(d.window_start)),
    end = Date.parse(beijing(d.window_end));
  if (
    !Number.isFinite(start) ||
    !Number.isFinite(end) ||
    typeof d.expected_duration_minutes !== "number" ||
    !Number.isInteger(d.expected_duration_minutes) ||
    d.expected_duration_minutes < 1 ||
    end - start < d.expected_duration_minutes * 60000
  )
    e.push("请填写能覆盖服务时长的有效时间窗口");
  if (d.fee_type !== "free" && d.fee_type !== "paid") e.push("请选择费用方式");
  for (const [k, label] of [
    ["location", "地点"],
    ["handover_notes", "交接方式"],
    ["emergency_contact", "异常联系人"],
  ] as const)
    if (!d[k].trim()) e.push("请填写" + label);
  const validMoney = /^\d{1,8}(\.\d{1,2})?$/.test(d.budget);
  if (d.service_type === "errand_buy" && (!validMoney || Number(d.budget) <= 0))
    e.push("代买商品预算须为大于0的有效金额");
  if (
    d.service_type !== "errand_buy" &&
    (!validMoney ||
      (d.fee_type === "paid" && Number(d.budget) <= 0) ||
      (d.fee_type === "free" && Number(d.budget) !== 0))
  )
    e.push("服务预算须为有效金额，无偿为0，有偿大于0");
  if (
    !d.checklist_items.length ||
    d.checklist_items.some(
      (i) => !i.content.trim() || !i.completion_condition.trim(),
    )
  )
    e.push("每项清单须填写内容与完成条件");
  if (
    d.checklist_items.some(
      (i) =>
        i.pet_id !== undefined &&
        i.pet_id !== null &&
        !d.pet_ids.includes(i.pet_id),
    )
  )
    e.push("清单项指定的宠物必须属于本次需求");
  if (
    d.service_type === "errand_buy" &&
    d.checklist_items.some(
      (i) =>
        i.item_key === "purchase" &&
        (!i.product_name?.trim() ||
          !Number.isInteger(i.quantity) ||
          i.quantity! < 1 ||
          !i.unit?.trim()),
    )
  )
    e.push("请填写商品名称、正整数数量与单位");
  return e;
}
export function payload(d: Draft): Draft {
  return {
    ...structuredClone(d),
    window_start: beijing(d.window_start),
    window_end: beijing(d.window_end),
    budget: Number(d.budget).toFixed(2),
    checklist_items: d.checklist_items.map((i, n) => ({
      ...i,
      position: n + 1,
    })),
  };
}

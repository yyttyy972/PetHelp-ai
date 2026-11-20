<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Api, ApiError } from "./api";
const props = defineProps<{
  api: Api;
  bookingId: string;
  requestId: string;
  version: number;
  bookingStatus: string;
  checklist: { item_key: string; content: string; execution_status?: string }[];
}>();
const emit = defineEmits<{ changed: [] }>();
const busy = ref(false),
  message = ref(""),
  items = ref<Record<string, unknown>[]>([]),
  events = ref<Record<string, unknown>[]>([]);
const reason = ref("other"),
  description = ref(""),
  proposalType = ref("none"),
  proposalValue = ref(""),
  note = ref(""),
  resolution = ref(""),
  decision = ref<"resume" | "end">("resume"),
  approvalType = ref("none"),
  approvalValue = ref(""),
  waive = ref<string[]>([]);
const openException = computed(
  () => items.value.find((x) => x.status === "open") || null,
);
const errors: Record<string, string> = {
  confirmation_pending: "变更已由宠主批准，正在等待帮手确认。",
  schedule_extension_required: "服务已超时，恢复前必须批准未来的结束时间。",
  executed_item_immutable: "已有证据或已完成的清单项不能修改。",
  invalid_change: "变更内容不符合规则，请核对预算、时间或清单。",
  time_conflict: "延期时间与帮手其他预约冲突。",
  version_conflict: "需求版本已更新，请刷新预约详情后再操作。",
  forbidden: "当前账号无权执行此操作。",
  invalid_state: "当前预约或异常状态不允许此操作。",
};
function change(type: string, value: string) {
  if (type === "none") return undefined;
  if (type === "budget") return { budget: Number(value) };
  if (type === "scheduled_end")
    return { scheduled_end: new Date(value).toISOString() };
  if (type === "precautions") return { precautions: value };
  if (type === "requirements") return { requirements: value };
  if (type === "waive") return { waive_item_keys: [...waive.value] };
  return undefined;
}
async function run(fn: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  message.value = "";
  try {
    await fn();
  } catch (e) {
    message.value =
      e instanceof ApiError
        ? errors[e.code] || e.message
        : e instanceof Error
          ? e.message
          : "操作失败";
  } finally {
    busy.value = false;
  }
}
async function load() {
  let cursor: string | undefined;
  const all: Record<string, unknown>[] = [];
  do {
    const data = (await props.api.bookingExceptions(
      props.bookingId,
      cursor,
    )) as { items: Record<string, unknown>[]; next_cursor: string | null };
    all.push(...data.items);
    cursor = data.next_cursor || undefined;
  } while (cursor);
  items.value = all;
  await loadEvents();
}
async function loadEvents() {
  let cursor: string | undefined;
  const all: Record<string, unknown>[] = [];
  do {
    const data = (await props.api.requestEvents(props.requestId, cursor)) as {
      items: Record<string, unknown>[];
      next_cursor: string | null;
    };
    all.push(...data.items);
    cursor = data.next_cursor || undefined;
  } while (cursor);
  events.value = all.filter((e) =>
    String(e.event_type).startsWith("exception_"),
  );
}
async function report() {
  if (!description.value.trim()) throw Error("请填写异常情况说明");
  const proposed = change(proposalType.value, proposalValue.value);
  await props.api.reportException(props.bookingId, {
    expected_version: props.version,
    reason_code: reason.value,
    description: description.value.trim(),
    ...(proposed ? { proposed_change: proposed } : {}),
  });
  message.value = "异常已上报，服务已暂停。";
  description.value = "";
  await load();
  emit("changed");
}
async function sendNote() {
  if (!openException.value || !note.value.trim()) throw Error("请填写沟通内容");
  await props.api.addExceptionNote(
    String(openException.value.id),
    note.value.trim(),
  );
  note.value = "";
  message.value = "沟通记录已保存。";
  await loadEvents();
}
async function resolve() {
  if (!openException.value || !resolution.value.trim())
    throw Error("请填写处理结论");
  const approved =
    decision.value === "resume"
      ? change(approvalType.value, approvalValue.value)
      : undefined;
  await props.api.resolveException(String(openException.value.id), {
    expected_version: props.version,
    resolution: resolution.value.trim(),
    decision: decision.value,
    ...(approved ? { approved_change: approved } : {}),
  });
  message.value =
    decision.value === "end"
      ? "服务已终止。"
      : approved
        ? "变更已批准，等待帮手确认新版本。"
        : "异常已解决，服务已恢复。";
  await load();
  emit("changed");
}
watch(
  () => [props.bookingId, props.bookingStatus, props.version],
  () => run(load),
);
onMounted(() => run(load));
</script>
<template>
  <article>
    <h2>异常处理</h2>
    <p role="status">{{ message }}</p>
    <fieldset :disabled="busy">
      <template v-if="!openException"
        ><label
          >异常类型<select v-model="reason">
            <option value="cannot_enter">无法进入</option>
            <option value="pet_hiding">宠物躲藏</option>
            <option value="service_timeout">服务超时</option>
            <option value="over_budget">超出预算</option>
            <option value="out_of_stock">商品缺货</option>
            <option value="verification_dispute">核验争议</option>
            <option value="other">其他</option>
          </select></label
        ><label>异常情况说明<textarea v-model="description" /></label
        ><label
          >建议调整<select v-model="proposalType">
            <option value="none">暂不建议变更</option>
            <option value="budget">预算</option>
            <option value="scheduled_end">预约结束时间</option>
            <option value="precautions">注意事项</option>
            <option value="requirements">服务要求</option>
          </select></label
        ><label v-if="proposalType !== 'none'"
          >建议值<input
            :type="
              proposalType === 'scheduled_end'
                ? 'datetime-local'
                : proposalType === 'budget'
                  ? 'number'
                  : 'text'
            "
            v-model="proposalValue" /></label
        ><button
          :disabled="
            !['reserved', 'in_service', 'pending_verify'].includes(
              bookingStatus,
            )
          "
          @click="run(report)"
        >
          上报异常并暂停服务
        </button></template
      ><template v-else
        ><p>
          {{ openException.reason_code }} · {{ openException.description }}
        </p>
        <p>
          状态：{{ openException.status }}；建议变更：{{
            openException.proposed_change || "无"
          }}
        </p>
        <label>追加沟通记录<textarea v-model="note" /></label
        ><button @click="run(sendNote)">保存沟通记录</button>
        <h3>宠主处理</h3>
        <label
          >处理决定<select v-model="decision">
            <option value="resume">解决后恢复</option>
            <option value="end">终止服务</option>
          </select></label
        ><label>处理结论<textarea v-model="resolution" /></label
        ><template v-if="decision === 'resume'"
          ><label
            >批准的变更<select v-model="approvalType">
              <option value="none">不变更</option>
              <option value="budget">预算</option>
              <option value="scheduled_end">预约结束时间</option>
              <option value="precautions">注意事项</option>
              <option value="requirements">服务要求</option>
              <option value="waive">豁免未执行清单项</option>
            </select></label
          ><label
            v-if="
              [
                'budget',
                'scheduled_end',
                'precautions',
                'requirements',
              ].includes(approvalType)
            "
            >批准值<input
              :type="
                approvalType === 'scheduled_end'
                  ? 'datetime-local'
                  : approvalType === 'budget'
                    ? 'number'
                    : 'text'
              "
              v-model="approvalValue" /></label
          ><template v-if="approvalType === 'waive'"
            ><label
              v-for="item in checklist"
              :key="item.item_key"
              class="inline"
              ><input
                type="checkbox"
                v-model="waive"
                :value="item.item_key"
                :disabled="
                  ['completed', 'waived'].includes(item.execution_status || '')
                "
              />{{ item.content }}</label
            ></template
          ></template
        ><button @click="run(resolve)">提交宠主决定</button>
        <p class="hint">
          批准重要变更后，帮手须再次确认新版本才能恢复。
        </p></template
      >
      <details>
        <summary>异常历史与沟通记录</summary>
        <ul>
          <li v-for="x in items" :key="String(x.id)">
            {{ x.reason_code }} · {{ x.status }} · {{ x.description }}
          </li>
        </ul>
        <ul>
          <li v-for="e in events" :key="String(e.id)">
            {{ e.event_type }} · {{ e.payload }}
          </li>
        </ul>
      </details>
    </fieldset>
  </article>
</template>

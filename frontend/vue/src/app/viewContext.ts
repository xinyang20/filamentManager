import { reactive, toRefs } from "vue";

export type AppViewContext = Record<string, any>;

export function composeViewContext(...fragments: Array<Record<string, any>>): AppViewContext {
  return reactive(Object.assign({}, ...fragments));
}

export function appViewRefs(ctx: AppViewContext) {
  return toRefs(ctx) as Record<string, any>;
}

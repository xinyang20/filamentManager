import { toRefs } from "vue";

export type AppViewContext = Record<string, any>;

export function appViewRefs(ctx: AppViewContext) {
  return toRefs(ctx) as Record<string, any>;
}

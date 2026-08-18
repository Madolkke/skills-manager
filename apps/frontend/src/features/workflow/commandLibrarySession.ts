import { ref } from "vue";

/** 命令库 Toggle 只在当前页面模块生命周期内复用，离开页面后由应用重载重置。 */
export const commandLibraryIncludeUser = ref(false);

export function resetCommandLibrarySession(): void {
  commandLibraryIncludeUser.value = false;
}

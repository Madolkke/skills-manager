<script setup lang="ts">
import { ADMIN_TABS } from "../lib/admin";
import AdminGroupsTab from "./admin/AdminGroupsTab.vue";
import AdminOpencodeAgentsTab from "./admin/AdminOpencodeAgentsTab.vue";
import AdminOverviewTab from "./admin/AdminOverviewTab.vue";
import AdminPublishTab from "./admin/AdminPublishTab.vue";
import AdminPublishTargetsTab from "./admin/AdminPublishTargetsTab.vue";
import AdminRoleAssignmentsTab from "./admin/AdminRoleAssignmentsTab.vue";
import AdminSkillTagsTab from "./admin/AdminSkillTagsTab.vue";
import AdminTagGroupsTab from "./admin/AdminTagGroupsTab.vue";
import AdminTagCascadesTab from "./admin/AdminTagCascadesTab.vue";
import AdminWorkersTab from "./admin/AdminWorkersTab.vue";
import AdminSystemCommandsTab from "./admin/AdminSystemCommandsTab.vue";
import { useAdminPageState } from "./admin/useAdminPageState";

const emit = defineEmits<{ toast: [toast: { tone: "success" | "danger" | "info"; message: string } | null] }>();
const {
  key, unlocked, loading, activeTab, skills, groups, tagGroups, roles, publishTargets, publishGateChecks,
  publishRecords, workerStatus, opencodeAgents, opencodeProviderCatalog, selectedGroupId, selectedTagGroupId,
  selectedOpencodeAgentId, tagDrafts, tagCascadeActions, adminActions, unlock, load, refreshWorkers,
  refreshOpencodeProviders, selectAdminTab, systemCommands, selectedSystemCommandId,
} = useAdminPageState((toast) => emit("toast", toast));
</script>

<template>
  <div class="admin-page">
    <section v-if="!unlocked" class="primary-panel admin-login">
      <h1>后台管理</h1>
      <p>输入后台密钥后访问管理能力。这个入口不属于普通权限体系。</p>
      <label class="field-label">
        <span>后台密钥</span>
        <input v-model="key" type="password" :disabled="loading" @keydown.enter="unlock" />
      </label>
      <button class="primary-button" type="button" :disabled="loading" @click="unlock">{{ loading ? "验证中..." : "进入后台" }}</button>
    </section>

    <template v-else>
      <div class="skill-nav-row admin-nav-row">
        <nav class="skill-tabs" aria-label="后台管理分类">
          <button
            v-for="tab in ADMIN_TABS"
            :key="tab.id"
            type="button"
            :class="['skill-tab', { active: activeTab === tab.id }]"
            @click="selectAdminTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </nav>
        <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>

      <Transition name="fade-slide" mode="out-in">
        <AdminOverviewTab v-if="activeTab === 'overview'" key="overview" :skills="skills" :groups="groups" :tag-groups="tagGroups" :roles="roles" />
        <AdminGroupsTab
          v-else-if="activeTab === 'groups'"
          key="groups"
          :groups="groups"
          :selected-group-id="selectedGroupId"
          @select="selectedGroupId = $event"
          @create="adminActions.createGroup"
          @update="adminActions.updateGroup"
          @delete="adminActions.deleteGroup"
          @add-member="adminActions.addGroupMember"
          @remove-member="adminActions.removeGroupMember"
        />
        <AdminTagGroupsTab
          v-else-if="activeTab === 'tag-groups'"
          key="tag-groups"
          :tag-groups="tagGroups"
          :selected-tag-group-id="selectedTagGroupId"
          @select="selectedTagGroupId = $event"
          @create-group="adminActions.createTagGroup"
          @update-group="adminActions.updateTagGroup"
          @delete-group="adminActions.deleteTagGroup"
          @create-value="adminActions.createTagValue"
          @update-value="adminActions.updateTagValue"
          @delete-value="adminActions.deleteTagValue"
        />
        <AdminRoleAssignmentsTab
          v-else-if="activeTab === 'roles'"
          key="roles"
          :roles="roles"
          :tag-groups="tagGroups"
          :skills="skills"
          @assign="adminActions.assignRole"
          @revoke="adminActions.revokeRole"
          @toast="emit('toast', { tone: 'danger', message: $event })"
        />
        <AdminTagCascadesTab
          v-else-if="activeTab === 'tag-cascades'"
          key="tag-cascades"
          :tag-groups="tagGroups"
          :overview="tagCascadeActions.overview.value"
          @attach="tagCascadeActions.attach"
          @detach="tagCascadeActions.detach"
          @inspect="tagCascadeActions.inspect"
        />
        <AdminSkillTagsTab
          v-else-if="activeTab === 'skill-tags'"
          key="skill-tags"
          :skills="skills"
          :tag-groups="tagGroups"
          :tag-drafts="tagDrafts"
          :focus="tagCascadeActions.focus.value"
          @update-draft="(skillId, tags) => { tagDrafts[skillId] = tags; }"
          @save="adminActions.saveSkillTags"
          @clear-focus="tagCascadeActions.focus.value = null"
        />
        <AdminWorkersTab
          v-else-if="activeTab === 'workers'"
          key="workers"
          :overview="workerStatus"
          :loading="loading"
          @refresh="refreshWorkers"
        />
        <AdminOpencodeAgentsTab
          v-else-if="activeTab === 'opencode-agents'"
          key="opencode-agents"
          :agents="opencodeAgents"
          :providers="opencodeProviderCatalog"
          :selected-agent-id="selectedOpencodeAgentId"
          @select="selectedOpencodeAgentId = $event"
          @refresh-providers="refreshOpencodeProviders"
          @create="adminActions.createOpencodeAgent"
          @update="adminActions.updateOpencodeAgent"
          @delete="adminActions.deleteOpencodeAgent"
        />
        <AdminSystemCommandsTab
          v-else-if="activeTab === 'system-commands'"
          key="system-commands"
          :commands="systemCommands"
          :selected-command-id="selectedSystemCommandId"
          @select="selectedSystemCommandId = $event"
          @create="adminActions.createSystemCommand"
          @update="adminActions.updateSystemCommand"
          @delete="adminActions.deleteSystemCommand"
        />
        <AdminPublishTargetsTab
          v-else-if="activeTab === 'publish-targets'"
          key="publish-targets"
          :targets="publishTargets"
          :checks="publishGateChecks"
          @update="adminActions.updatePublishTarget"
        />
        <AdminPublishTab
          v-else
          key="publish"
          :records="publishRecords"
          @confirm-record="adminActions.confirmPublishRecord"
          @cancel-record="adminActions.cancelPublishRecord"
          @retry-record="adminActions.retryPublishRecord"
          @batch-confirm="adminActions.batchConfirmPublishRecords"
          @batch-cancel="adminActions.batchCancelPublishRecords"
        />
      </Transition>
    </template>
  </div>
</template>

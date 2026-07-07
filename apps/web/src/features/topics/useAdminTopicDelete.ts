import { message, Modal } from "ant-design-vue";
import { ref } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { useContentDeleteMutation } from "@/features/moderation/queries";

interface AdminTopicDeleteOptions {
  note?: string;
  successMessage?: string;
  onDeleted?: (topic: TopicCardVM) => void | Promise<void>;
}

const DEFAULT_DELETE_NOTE = "前台管理员删除主题。";

/**
 * Builds the reusable public-surface topic deletion flow for administrators.
 *
 * @param defaults - Optional audit note, success copy, and success callback shared by one page.
 * @returns Delete request handler plus the currently pending topic id; side effects show confirmation, call moderation delete, refresh caches, and display feedback.
 */
export function useAdminTopicDelete(defaults: AdminTopicDeleteOptions = {}) {
  const deletingTopicId = ref<string | null>(null);
  const deleteMutation = useContentDeleteMutation({ awaitInvalidation: false });

  /**
   * Opens a destructive confirmation and deletes the selected topic if confirmed.
   *
   * @param topic - Public topic card selected from a list or detail page.
   * @param options - Per-call audit note, success copy, and callback overrides.
   * @returns Nothing; side effects hide the topic through moderation endpoints and show user feedback.
   */
  function requestDeleteTopic(topic: TopicCardVM, options: AdminTopicDeleteOptions = {}) {
    if (deletingTopicId.value) {
      return;
    }

    const mergedOptions = { ...defaults, ...options };
    Modal.confirm({
      title: "删除这个主题？",
      content: `删除后「${topic.title}」会从公开列表和详情页隐藏，并留下审核记录。`,
      okText: "删除",
      cancelText: "取消",
      okType: "danger",
      centered: true,
      onOk: async () => {
        deletingTopicId.value = topic.id;
        try {
          await deleteMutation.mutateAsync({
            targetType: "topic",
            targetId: topic.id,
            note: mergedOptions.note ?? DEFAULT_DELETE_NOTE,
          });
          void message.success(mergedOptions.successMessage ?? "主题已删除。");
          await mergedOptions.onDeleted?.(topic);
        } catch {
          void message.error("删除失败，请确认管理员权限后重试。");
        } finally {
          deletingTopicId.value = null;
        }
      },
    });
  }

  return {
    deletingTopicId,
    requestDeleteTopic,
  };
}

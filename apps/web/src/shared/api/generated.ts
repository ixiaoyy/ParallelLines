// Generated from apps/api/openapi/openapi.json by apps/web/scripts/generate-openapi-types.mjs.
// Do not edit by hand. Run: pnpm --dir apps/web openapi:types

export interface components {
  schemas: {
    AdminBackgroundJobLogResponse: {
      created_at: string;
      data: {
      [key: string]: unknown;
    };
      event: string;
      id: string;
      job_id: string;
      message: string;
    };
    AdminBackgroundJobResponse: {
      attempts: number;
      created_at: string;
      finished_at?: string | null;
      id: string;
      idempotency_key?: string | null;
      last_error?: string | null;
      locked_at?: string | null;
      locked_by?: string | null;
      max_attempts: number;
      priority: number;
      queue: string;
      result?: {
      [key: string]: unknown;
    } | null;
      run_at: string;
      status: string;
      task_name: string;
      updated_at: string;
    };
    AdminEmailLogResponse: {
      kind: string;
      sent_at: string;
      subject: string;
      to_email: string;
    };
    AdminServiceStatusResponse: {
      detail: string;
      name: string;
      status: "ok" | "degraded" | "unknown";
    };
    AdminStatsResponse: {
      audit_logs: number;
      boards: number;
      pending_flags: number;
      posts: number;
      spam_actions: number;
      topics: number;
      users: number;
    };
    AdminSystemOverviewResponse: {
      environment: string;
      queue: {
      [key: string]: unknown;
    };
      recent_audit_logs: Array<components["schemas"]["AuditLogResponse"]>;
      recent_email_logs: Array<components["schemas"]["AdminEmailLogResponse"]>;
      recent_errors: Array<{
      [key: string]: unknown;
    }>;
      services: Array<components["schemas"]["AdminServiceStatusResponse"]>;
      stats: components["schemas"]["AdminStatsResponse"];
      version: string;
    };
    AdminUserResponse: {
      avatar_url?: string | null;
      badges?: Array<components["schemas"]["UserBadgeResponse"]>;
      created_at: string;
      email: string;
      experience_to_next_level: number;
      experience_total: number;
      id: string;
      last_seen_at?: string | null;
      level: number;
      level_progress_percent: number;
      points_balance: number;
      post_count: number;
      role: string;
      status: string;
      topic_count: number;
      trust_level: number;
      trust_level_label: string;
      two_factor_enabled: boolean;
      updated_at: string;
      username: string;
    };
    AdminUserUpdateRequest: {
      adjustment_reason?: string | null;
      experience_delta?: number | null;
      level?: number | null;
      points_delta?: number | null;
      role?: "user" | "moderator" | "admin" | null;
      status?: "active" | "silenced" | "suspended" | "deleted" | null;
    };
    AnalyticsMetricPoint: {
      dau?: number;
      day: string;
      flags?: number;
      likes?: number;
      posts?: number;
      registrations?: number;
      topics?: number;
    };
    AnalyticsOverviewResponse: {
      end_date: string;
      series: Array<components["schemas"]["AnalyticsMetricPoint"]>;
      start_date: string;
      top_boards: Array<components["schemas"]["AnalyticsTopBoardResponse"]>;
      top_topics: Array<components["schemas"]["AnalyticsTopTopicResponse"]>;
      top_users: Array<components["schemas"]["AnalyticsTopUserResponse"]>;
      totals: components["schemas"]["AnalyticsTotalsResponse"];
    };
    AnalyticsTopBoardResponse: {
      id: string;
      name: string;
      post_count: number;
      slug: string;
      topic_count: number;
    };
    AnalyticsTopTopicResponse: {
      board_slug: string;
      id: string;
      like_count: number;
      reply_count: number;
      slug: string;
      title: string;
      view_count: number;
    };
    AnalyticsTopUserResponse: {
      id: string;
      points_balance: number;
      post_count: number;
      topic_count: number;
      username: string;
    };
    AnalyticsTotalsResponse: {
      dau: number;
      flags: number;
      likes: number;
      mau: number;
      posts: number;
      registrations: number;
      topics: number;
    };
    ApiKeyCreateRequest: {
      expires_at?: string | null;
      name: string;
      note?: string | null;
      owner_user_id?: string | null;
      scopes?: Array<string>;
    };
    ApiKeyCreateResponse: {
      api_key: components["schemas"]["ApiKeyResponse"];
      token: string;
    };
    ApiKeyResponse: {
      created_at: string;
      created_by_id?: string | null;
      disabled_at?: string | null;
      expires_at?: string | null;
      id: string;
      key_type: string;
      last_used_at?: string | null;
      name: string;
      note?: string | null;
      owner_user_id?: string | null;
      scopes: Array<string>;
      token_prefix: string;
      updated_at: string;
    };
    ApiResponse_AdminSystemOverviewResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_AdminUserResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_AnalyticsOverviewResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ApiKeyCreateResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ApiKeyResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BackupArtifactResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BackupRestoreResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BoardDetailResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BoardFollowResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BoardInviteResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BoardMemberRemoveResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BoardMemberResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BoardResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_BoardSettingsResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_bool_: {
      [key: string]: unknown;
    };
    ApiResponse_DataExplorerReportResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_dict_str__bool__: {
      [key: string]: unknown;
    };
    ApiResponse_dict_str__int__: {
      [key: string]: unknown;
    };
    ApiResponse_dict_str__str__: {
      [key: string]: unknown;
    };
    ApiResponse_DraftResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_EmailChangeStartResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_EmailDeliveryEventResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_EmailPreferenceResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_EventResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_EventRsvpResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ExternalIntegrationEventResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ExternalIntegrationResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ExternalWebhookResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_FlagResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_FrontierNewsCollectResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_FrontierNewsItemResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_FrontierNewsSourceResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_GitHubIssuePreviewResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_InboundEmailResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_InteractionStateResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_list_AdminBackgroundJobLogResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_AdminBackgroundJobResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_AdminEmailLogResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_AdminUserResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_ApiKeyResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_AuditLogResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_BackupArtifactResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_BadgeResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_BoardResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_DataExplorerReportSummary__: {
      [key: string]: unknown;
    };
    ApiResponse_list_DraftResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_EventResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_ExternalIntegrationEventResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_ExternalIntegrationResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_FlagResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_FrontierNewsItemResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_FrontierNewsSourceResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_ImmersiveTopicFeedItemResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_PluginResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_PluginUiExtensionResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_PostResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_PostRevisionResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_PrivateMessageTopicResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_ReviewableResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_ScreenedRuleResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_SessionResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_SimilarTopicResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_SiteSettingResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_SpamActionResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_TagResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_TopicResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_UserActivityItemResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_UserDirectoryResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_UserRelationshipUserResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_WebhookDeliveryResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_list_WebhookEndpointResponse__: {
      [key: string]: unknown;
    };
    ApiResponse_LoginResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_MigrationExportResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_MigrationImportResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ModerationActionResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ModerationAdviceResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_MyBoardInvitesResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_NotificationListResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_NotificationReadResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_OAuthProviderResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PasswordResetStartResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PluginResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PollResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PostResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PostRevisionResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PrivacyActionResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PrivateMessageTopicResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PublicApiDocsResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PublicSiteSettingsResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_PushSubscriptionStateResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_RegistrationStartResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_RetentionPolicyResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ReviewableBulkDecisionResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ReviewableResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_ScreenedRuleResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_SeoMetaResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_SiteSettingResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TokenPair_: {
      [key: string]: unknown;
    };
    ApiResponse_TopicAiSummaryResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TopicLifecycleResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TopicLocalizationResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TopicNotificationLevelResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TopicReadStateResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TopicResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TwoFactorRecoveryCodesResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_TwoFactorSetupResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_Union_DraftResponse__NoneType__: {
      [key: string]: unknown;
    };
    ApiResponse_UploadResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_UserProfileResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_UserPublic_: {
      [key: string]: unknown;
    };
    ApiResponse_UserRelationshipStateResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_UserStatusResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_VoteStateResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_WebhookEndpointCreateResponse_: {
      [key: string]: unknown;
    };
    ApiResponse_WebhookEndpointResponse_: {
      [key: string]: unknown;
    };
    AuditLogResponse: {
      action: string;
      actor_id?: string | null;
      actor_name?: string | null;
      board_id?: string | null;
      created_at: string;
      data: {
      [key: string]: unknown;
    };
      id: string;
      target_id: string;
      target_type: string;
    };
    BackupArtifactResponse: {
      byte_size?: number | null;
      completed_at?: string | null;
      created_at: string;
      created_by_id?: string | null;
      created_by_name?: string | null;
      failure_reason?: string | null;
      filename: string;
      id: string;
      kind: string;
      metadata: {
      [key: string]: unknown;
    };
      sha256?: string | null;
      status: string;
      storage_backend: string;
      storage_key?: string | null;
      updated_at: string;
    };
    BackupCreateRequest: {
      include_uploads?: boolean;
    };
    BackupRestoreRequest: {
      confirmation: string;
    };
    BackupRestoreResponse: {
      backup_id: string;
      message: string;
      restore_supported: boolean;
      status: "validated";
      verified_checksum: boolean;
    };
    BadgeGrantRequest: {
      badge_slug: string;
      note?: string | null;
    };
    BadgeResponse: {
      active: boolean;
      category: string;
      created_at: string;
      description: string;
      icon: string;
      id: string;
      name: string;
      slug: string;
      trust_level_required: number;
      updated_at: string;
    };
    BadgeRevokeRequest: {
      reason?: string | null;
    };
    BoardCreateRequest: {
      allowed_tags?: Array<string>;
      color?: string;
      default_notification_level?: "muted" | "normal" | "tracking" | "watching";
      default_sort?: "latest" | "hot" | "top";
      description: string;
      name: string;
      parent_board_id?: string | null;
      parent_board_slug?: string | null;
      post_template?: string | null;
      required_tags?: Array<string>;
      slug: string;
      visibility?: "public" | "private" | "unlisted";
    };
    BoardDetailResponse: {
      allowed_tags?: Array<string>;
      avatar_url?: string | null;
      can_create_topic?: boolean;
      child_boards?: Array<components["schemas"]["BoardResponse"]>;
      color: string;
      created_at: string;
      default_notification_level: "muted" | "normal" | "tracking" | "watching";
      default_sort: "latest" | "hot" | "top";
      description: string;
      follower_count: number;
      id: string;
      is_following?: boolean;
      latest_topics: Array<components["schemas"]["TopicResponse"]>;
      name: string;
      name_localizations?: {
      [key: string]: string;
    };
      notification_level?: "muted" | "normal" | "tracking" | "watching" | null;
      owner_id?: string | null;
      parent_board_id?: string | null;
      parent_board_name?: string | null;
      parent_board_slug?: string | null;
      post_count: number;
      post_template?: string | null;
      required_tags?: Array<string>;
      slug: string;
      topic_count: number;
      updated_at: string;
      visibility: string;
    };
    BoardFollowRequest: {
      notification_level?: "muted" | "normal" | "tracking" | "watching" | null;
    };
    BoardFollowResponse: {
      board_id: string;
      board_slug: string;
      follower_count: number;
      following: boolean;
      notification_level: "muted" | "normal" | "tracking" | "watching" | null;
      role: string | null;
    };
    BoardInviteCreateRequest: {
      board_id: string;
      username: string;
    };
    BoardInviteResponse: {
      board_color: string;
      board_description: string;
      board_id: string;
      board_name: string;
      board_slug: string;
      created_at: string;
      expires_at?: string | null;
      id: string;
      invitee_id: string;
      invitee_name: string;
      inviter_id: string;
      inviter_name: string;
      responded_at?: string | null;
      status: string;
      updated_at: string;
    };
    BoardMemberRemoveResponse: {
      board_id: string;
      removed: boolean;
      username: string;
    };
    BoardMemberResponse: {
      joined_at: string;
      notification_level: "muted" | "normal" | "tracking" | "watching";
      role: string;
      user_id: string;
      username: string;
    };
    BoardMemberUpdateRequest: {
      notification_level?: "muted" | "normal" | "tracking" | "watching" | null;
      role: "follower" | "moderator";
    };
    BoardResponse: {
      allowed_tags?: Array<string>;
      avatar_url?: string | null;
      can_create_topic?: boolean;
      color: string;
      created_at: string;
      default_notification_level: "muted" | "normal" | "tracking" | "watching";
      default_sort: "latest" | "hot" | "top";
      description: string;
      follower_count: number;
      id: string;
      is_following?: boolean;
      name: string;
      name_localizations?: {
      [key: string]: string;
    };
      notification_level?: "muted" | "normal" | "tracking" | "watching" | null;
      owner_id?: string | null;
      parent_board_id?: string | null;
      parent_board_name?: string | null;
      parent_board_slug?: string | null;
      post_count: number;
      post_template?: string | null;
      required_tags?: Array<string>;
      slug: string;
      topic_count: number;
      updated_at: string;
      visibility: string;
    };
    BoardSettingsResponse: {
      board: components["schemas"]["BoardResponse"];
      members: Array<components["schemas"]["BoardMemberResponse"]>;
    };
    BoardSettingsUpdateRequest: {
      allowed_tags?: Array<string>;
      default_notification_level?: "muted" | "normal" | "tracking" | "watching";
      default_sort?: "latest" | "hot" | "top";
      parent_board_id?: string | null;
      parent_board_slug?: string | null;
      post_template?: string | null;
      required_tags?: Array<string>;
    };
    Body_upload_avatar_api_v1_uploads_avatar_post: {
      file: string;
    };
    Body_upload_file_api_v1_uploads_post: {
      file: string;
      kind?: "post_attachment" | "avatar";
    };
    ChangePasswordRequest: {
      current_password: string;
      new_password: string;
    };
    DataExplorerReportResponse: {
      columns?: Array<string>;
      description: string;
      id: string;
      name: string;
      rows?: Array<{
      [key: string]: unknown;
    }>;
    };
    DataExplorerReportSummary: {
      columns?: Array<string>;
      description: string;
      id: string;
      name: string;
    };
    DraftResponse: {
      created_at: string;
      data: {
      [key: string]: unknown;
    };
      draft_type: string;
      id: string;
      target_id: string;
      target_type: string;
      updated_at: string;
      user_id: string;
      version: number;
    };
    DraftSaveRequest: {
      data?: {
      [key: string]: unknown;
    };
      draft_type: string;
      target_id?: string;
      target_type: string;
      version?: number;
    };
    EmailChangeConfirmRequest: {
      token: string;
    };
    EmailChangeRequest: {
      new_email: string;
      password: string;
    };
    EmailChangeStartResponse: {
      email: string;
      expires_in_seconds: number;
    };
    EmailDeliveryEventResponse: {
      created_at: string;
      email: string;
      event_type: string;
      id: string;
      kind?: string | null;
      provider_message_id?: string | null;
      reason?: string | null;
      user_id?: string | null;
    };
    EmailDeliveryWebhookRequest: {
      email: string;
      event_type: "delivered" | "bounce" | "complaint" | "dropped";
      kind?: string | null;
      payload?: {
      [key: string]: unknown;
    };
      provider_message_id?: string | null;
      reason?: string | null;
    };
    EmailPreferenceResponse: {
      delivery_status: string;
      digest_frequency: string;
      disabled_reason?: string | null;
      email_enabled: boolean;
      last_digest_sent_at?: string | null;
      notify_board_new_topic: boolean;
      notify_liked: boolean;
      notify_mentioned: boolean;
      notify_replied: boolean;
      notify_topic_new_post: boolean;
      quiet_hours_end?: number | null;
      quiet_hours_start?: number | null;
      updated_at: string;
    };
    EmailPreferenceUpdateRequest: {
      digest_frequency?: "off" | "daily" | "weekly" | null;
      email_enabled?: boolean | null;
      notify_board_new_topic?: boolean | null;
      notify_liked?: boolean | null;
      notify_mentioned?: boolean | null;
      notify_replied?: boolean | null;
      notify_topic_new_post?: boolean | null;
      quiet_hours_end?: number | null;
      quiet_hours_start?: number | null;
    };
    ErrorPayload: {
      code: string;
      details?: {
      [key: string]: unknown;
    };
      message: string;
    };
    ErrorResponse: {
      error: components["schemas"]["ErrorPayload"];
    };
    EventCreateRequest: {
      capacity?: number | null;
      description?: string | null;
      end_at: string;
      location?: string | null;
      reminder_minutes_before?: number;
      rsvp_deadline?: string | null;
      start_at: string;
      timezone?: string;
      title: string;
      topic_id?: string | null;
    };
    EventLifecycleRequest: {
      status: "scheduled" | "canceled";
    };
    EventResponse: {
      capacity?: number | null;
      created_at: string;
      created_by_id: string;
      description?: string | null;
      end_at: string;
      going_count: number;
      id: string;
      location?: string | null;
      my_rsvp_status?: string | null;
      reminder_minutes_before: number;
      rsvp_deadline?: string | null;
      start_at: string;
      status: "scheduled" | "canceled";
      timezone: string;
      title: string;
      topic_id?: string | null;
    };
    EventRsvpRequest: {
      status?: "going" | "canceled";
    };
    EventRsvpResponse: {
      reminder_sent_at?: string | null;
      status: string;
      user_id: string;
      username: string;
    };
    ExternalIntegrationEventResponse: {
      action?: string | null;
      created_at: string;
      event_id: string;
      event_type: string;
      external_url?: string | null;
      id: string;
      last_error?: string | null;
      linked_resource_id?: string | null;
      linked_resource_type?: string | null;
      max_retries: number;
      next_retry_at?: string | null;
      processed_at?: string | null;
      provider: string;
      retry_count: number;
      signature_valid: boolean;
      status: string;
      title?: string | null;
      updated_at: string;
    };
    ExternalIntegrationResponse: {
      config: {
      [key: string]: unknown;
    };
      enabled: boolean;
      issues: Array<string>;
      last_checked_at?: string | null;
      last_error?: string | null;
      provider: string;
      required_config: Array<string>;
      status: "disabled" | "healthy" | "misconfigured" | "error" | string;
      updated_at?: string | null;
    };
    ExternalIntegrationUpdateRequest: {
      config?: {
      [key: string]: unknown;
    };
      enabled?: boolean;
    };
    ExternalWebhookResponse: {
      event_id: string;
      event_type: string;
      processed: boolean;
      provider: string;
      retry_count?: number;
      status: string;
    };
    FlagCreateRequest: {
      detail?: string | null;
      reason?: "spam" | "harassment" | "off_topic" | "private_info" | "other";
      target_id: string;
      target_type: "topic" | "post";
    };
    FlagResponse: {
      board_id: string;
      created_at: string;
      detail?: string | null;
      id: string;
      reason: string;
      reporter_id: string;
      reporter_name: string;
      resolution_note?: string | null;
      resolved_at?: string | null;
      resolved_by_id?: string | null;
      status: string;
      target: components["schemas"]["ModerationTargetResponse"];
      target_id: string;
      target_type: string;
      updated_at: string;
    };
    FlagStatusUpdateRequest: {
      resolution_note?: string | null;
      status: "pending" | "resolved" | "rejected";
    };
    FrontierNewsCollectResponse: {
      created_count: number;
      error_count: number;
      queued_count: number;
      skipped_count: number;
      source_count: number;
    };
    FrontierNewsItemQueueRequest: {
      note?: string | null;
    };
    FrontierNewsItemResponse: {
      ai_error?: string | null;
      ai_key_points: Array<string>;
      ai_model_name?: string | null;
      ai_processed_at?: string | null;
      ai_review_suggestion?: string | null;
      ai_risk_flags: Array<string>;
      ai_summary_zh?: string | null;
      ai_title_zh?: string | null;
      ai_why_it_matters?: string | null;
      author_names: Array<string>;
      canonical_url: string;
      created_at: string;
      external_id: string;
      id: string;
      item_type: string;
      published_at?: string | null;
      review_note?: string | null;
      reviewable_id?: string | null;
      reviewed_at?: string | null;
      reviewed_by_id?: string | null;
      reviewed_by_name?: string | null;
      score: number;
      source_id: string;
      source_name?: string | null;
      status: string;
      suggested_tags: Array<string>;
      summary?: string | null;
      title: string;
      topic_id?: string | null;
      updated_at: string;
    };
    FrontierNewsSourceCreateRequest: {
      config?: {
      [key: string]: unknown;
    };
      enabled?: boolean;
      fetch_interval_minutes?: number;
      key: string;
      kind: "rss" | "arxiv" | "hacker_news" | "github_search" | "xai_news" | "arena_leaderboard" | "news_html_index";
      name: string;
      trust_level?: number;
      url: string;
    };
    FrontierNewsSourceResponse: {
      config: {
      [key: string]: unknown;
    };
      created_at: string;
      enabled: boolean;
      fetch_interval_minutes: number;
      id: string;
      key: string;
      kind: string;
      last_checked_at?: string | null;
      last_error?: string | null;
      name: string;
      trust_level: number;
      updated_at: string;
      url: string;
    };
    FrontierNewsSourceUpdateRequest: {
      config?: {
      [key: string]: unknown;
    } | null;
      enabled?: boolean | null;
      fetch_interval_minutes?: number | null;
      name?: string | null;
      trust_level?: number | null;
      url?: string | null;
    };
    GitHubIssuePreviewResponse: {
      number: number;
      owner: string;
      repo: string;
      source: "webhook_cache" | "parsed_url";
      state?: string | null;
      title: string;
      url: string;
    };
    HideContentRequest: {
      note?: string | null;
    };
    HTTPValidationError: {
      detail?: Array<components["schemas"]["ValidationError"]>;
    };
    ImmersiveTopicFeedItemResponse: {
      lead_post?: components["schemas"]["PostResponse"] | null;
      read_state: components["schemas"]["TopicReadStateResponse"];
      topic: components["schemas"]["TopicResponse"];
    };
    InboundEmailResponse: {
      created_at: string;
      from_email: string;
      id: string;
      post_id?: string | null;
      provider_message_id?: string | null;
      reason?: string | null;
      status: string;
      topic_id?: string | null;
      user_id?: string | null;
    };
    InboundEmailWebhookRequest: {
      from_email: string;
      payload?: {
      [key: string]: unknown;
    };
      post_id?: string | null;
      provider_message_id?: string | null;
      raw_md: string;
      topic_id?: string | null;
    };
    InteractionStateResponse: {
      active: boolean;
      count: number;
      target_id: string;
      target_type: "post" | "topic";
    };
    LoginRequest: {
      account: string;
      password: string;
    };
    LoginResponse: {
      access_token?: string | null;
      challenge_token?: string | null;
      refresh_token?: string | null;
      session_id?: string | null;
      token_type?: string;
      two_factor_required?: boolean;
      user?: components["schemas"]["UserPublic"] | null;
    };
    MigrationBoardRecord: {
      color?: string;
      description?: string;
      name: string;
      slug: string;
    };
    MigrationExportResponse: {
      boards: Array<{
      [key: string]: unknown;
    }>;
      exported_at: string;
      posts: Array<{
      [key: string]: unknown;
    }>;
      tags: Array<{
      [key: string]: unknown;
    }>;
      topics: Array<{
      [key: string]: unknown;
    }>;
      users: Array<{
      [key: string]: unknown;
    }>;
    };
    MigrationImportRequest: {
      boards?: Array<components["schemas"]["MigrationBoardRecord"]>;
      posts?: Array<components["schemas"]["MigrationPostRecord"]>;
      source?: string;
      topics?: Array<components["schemas"]["MigrationTopicRecord"]>;
      users?: Array<components["schemas"]["MigrationUserRecord"]>;
    };
    MigrationImportResponse: {
      created: number;
      dry_run: boolean;
      errors: number;
      rows: Array<components["schemas"]["MigrationRowResult"]>;
      skipped: number;
      source: string;
      updated: number;
    };
    MigrationPostRecord: {
      author_username: string;
      board_slug: string;
      created_at?: string | null;
      post_number: number;
      raw_md: string;
      topic_external_id?: string | null;
      topic_slug?: string | null;
    };
    MigrationRowResult: {
      action: "created" | "updated" | "skipped" | "error" | string;
      key: string;
      message: string;
      resource: "user" | "board" | "topic" | "post" | "tag" | string;
    };
    MigrationTopicRecord: {
      author_username: string;
      board_slug: string;
      created_at?: string | null;
      external_id?: string | null;
      raw_md?: string;
      slug?: string | null;
      tags?: Array<string>;
      title: string;
    };
    MigrationUserRecord: {
      display_name?: string | null;
      email: string;
      username: string;
    };
    ModerationActionResponse: {
      hidden: boolean;
      status?: string | null;
      target_id: string;
      target_type: string;
    };
    ModerationAdviceRequest: {
      raw_text: string;
      reason?: string | null;
      target_type?: "topic" | "post" | "profile" | "message" | string;
      title?: string | null;
    };
    ModerationAdviceResponse: {
      auto_action_allowed?: boolean;
      cost_units: number;
      reasons: Array<string>;
      requires_human_review?: boolean;
      risk_level: "low" | "medium" | "high";
      suggested_actions: Array<string>;
      summary: string;
    };
    ModerationTargetResponse: {
      author_id: string;
      author_name: string;
      board_id: string;
      board_name: string;
      board_slug: string;
      excerpt: string;
      hidden: boolean;
      post_number?: number | null;
      target_id: string;
      target_type: string;
      title: string;
      topic_id?: string | null;
      topic_slug?: string | null;
    };
    MyBoardInvitesResponse: {
      managed: Array<components["schemas"]["BoardInviteResponse"]>;
      owned_boards: Array<components["schemas"]["BoardResponse"]>;
      received: Array<components["schemas"]["BoardInviteResponse"]>;
    };
    NotificationListResponse: {
      notifications: Array<components["schemas"]["NotificationResponse"]>;
      unread_count: number;
    };
    NotificationReadRequest: {
      ids?: Array<string> | null;
    };
    NotificationReadResponse: {
      unread_count: number;
      updated_count: number;
    };
    NotificationResponse: {
      actor_id?: string | null;
      actor_name?: string | null;
      created_at: string;
      data: {
      [key: string]: unknown;
    };
      id: string;
      post_id?: string | null;
      read_at?: string | null;
      topic_id?: string | null;
      type: string;
    };
    OAuthProviderResponse: {
      providers: Array<string>;
    };
    PasswordResetConfirmRequest: {
      email?: string | null;
      new_password: string;
      token: string;
    };
    PasswordResetRequest: {
      email: string;
    };
    PasswordResetStartResponse: {
      expires_in_seconds: number;
      ok?: boolean;
    };
    PluginResponse: {
      config?: {
      [key: string]: unknown;
    };
      description: string;
      enabled: boolean;
      events: Array<string>;
      id: string;
      name: string;
      ui_extensions: Array<components["schemas"]["PluginUiExtensionResponse"]>;
      version: string;
    };
    PluginUiExtensionResponse: {
      component: string;
      description: string;
      key: string;
      plugin_id: string;
      props?: {
      [key: string]: unknown;
    };
      slot: string;
      title: string;
    };
    PluginUpdateRequest: {
      config?: {
      [key: string]: unknown;
    };
      enabled: boolean;
    };
    PollCreateRequest: {
      closes_at?: string | null;
      multiple_choice?: boolean;
      options: Array<string>;
      question: string;
    };
    PollOptionResponse: {
      id: string;
      label: string;
      position: number;
      vote_count: number;
    };
    PollResponse: {
      closed: boolean;
      closes_at?: string | null;
      created_at: string;
      id: string;
      multiple_choice: boolean;
      options: Array<components["schemas"]["PollOptionResponse"]>;
      question: string;
      selected_option_ids?: Array<string>;
      topic_id: string;
      total_votes: number;
      updated_at: string;
    };
    PollVoteRequest: {
      option_ids?: Array<string>;
    };
    PostCreateRequest: {
      parent_post_id?: string | null;
      raw_md: string;
    };
    PostResponse: {
      accepted_answer?: boolean;
      author_avatar_url?: string | null;
      author_level: number;
      author_name: string;
      author_role: string;
      author_trust_level: number;
      author_trust_level_label: string;
      cooked_html: string;
      created_at: string;
      deleted_at?: string | null;
      id: string;
      like_count: number;
      liked_by_me?: boolean;
      my_vote?: number;
      parent_id?: string | null;
      post_number: number;
      raw_md: string;
      reply_count: number;
      share_url: string;
      topic_id: string;
      updated_at: string;
      user_id: string;
      vote_count?: number;
      vote_score?: number;
    };
    PostRevisionResponse: {
      cooked_html: string;
      created_at: string;
      edit_reason?: string | null;
      editor_id?: string | null;
      editor_name?: string | null;
      id: string;
      post_id: string;
      raw_md: string;
      restored_from_revision_id?: string | null;
      summary: string;
      topic_id: string;
      version_number: number;
    };
    PostRevisionRestoreRequest: {
      reason?: string | null;
    };
    PostUpdateRequest: {
      edit_reason?: string | null;
      raw_md: string;
    };
    PrivacyActionRequest: {
      reason?: string | null;
    };
    PrivacyActionResponse: {
      anonymized: boolean;
      anonymized_logs?: number;
      deleted_drafts?: number;
      deleted_email_codes?: number;
      deleted_notifications?: number;
      deleted_recovery_codes?: number;
      deleted_security_tokens?: number;
      deleted_uploads?: number;
      disabled_api_keys?: number;
      disabled_webhooks?: number;
      email: string;
      reason?: string | null;
      removed_board_invitations?: number;
      removed_board_memberships?: number;
      removed_private_message_participations?: number;
      removed_relationships?: number;
      retained_uploads?: number;
      revoked_sessions?: number;
      status: string;
      user_id: string;
      username: string;
    };
    PrivateMessageCreateRequest: {
      participant_usernames: Array<string>;
      raw_md: string;
      title: string;
    };
    PrivateMessageParticipantResponse: {
      last_read_post_number: number;
      muted: boolean;
      role: string;
      user_id: string;
      username: string;
    };
    PrivateMessageTopicResponse: {
      participants: Array<components["schemas"]["PrivateMessageParticipantResponse"]>;
      topic: components["schemas"]["TopicResponse"];
      unread: boolean;
    };
    PublicApiDocsResponse: {
      api_version: string;
      authentication: {
      [key: string]: string;
    };
      compatibility_policy: {
      [key: string]: unknown;
    };
      error_shape: {
      [key: string]: unknown;
    };
      examples?: Array<components["schemas"]["PublicApiExample"]>;
      openapi_url: string;
      pagination: {
      [key: string]: unknown;
    };
    };
    PublicApiExample: {
      request: {
      [key: string]: unknown;
    };
      response: {
      [key: string]: unknown;
    };
      title: string;
    };
    PublicSiteSettingsResponse: {
      settings: {
      [key: string]: unknown;
    };
      updated_at?: string | null;
    };
    PushSubscriptionKeys: {
      auth: string;
      p256dh: string;
    };
    PushSubscriptionRequest: {
      endpoint: string;
      keys: components["schemas"]["PushSubscriptionKeys"];
      user_agent?: string | null;
    };
    PushSubscriptionResponse: {
      created_at: string;
      disabled_at?: string | null;
      enabled: boolean;
      endpoint_excerpt: string;
      id: string;
      last_sent_at?: string | null;
      updated_at: string;
      user_agent?: string | null;
    };
    PushSubscriptionStateResponse: {
      preference_hint?: string;
      subscription?: components["schemas"]["PushSubscriptionResponse"] | null;
      supported?: boolean;
    };
    RefreshRequest: {
      refresh_token: string;
    };
    RegisterRequest: {
      email: string;
      password: string;
      username: string;
    };
    RegistrationStartResponse: {
      dev_verification_code?: string | null;
      email: string;
      expires_in_seconds: number;
      resend_after_seconds: number;
      verification_required?: boolean;
    };
    ResendVerificationRequest: {
      email: string;
    };
    RetentionPolicyResponse: {
      account_deletion_mode: string;
      export_redaction: string;
      removed_private_data: string;
      retained_content: string;
      upload_retention: string;
      user_export_available: boolean;
    };
    ReviewableAppealRequest: {
      reason: string;
    };
    ReviewableBulkDecisionRequest: {
      action: "approve" | "reject" | "hide" | "delete" | "silence" | "escalate";
      note?: string | null;
      reviewable_ids: Array<string>;
    };
    ReviewableBulkDecisionResponse: {
      action: "approve" | "reject" | "hide" | "delete" | "silence" | "escalate";
      processed_count: number;
      requested_count: number;
      reviewables: Array<components["schemas"]["ReviewableResponse"]>;
    };
    ReviewableDecisionRequest: {
      action: "approve" | "reject" | "hide" | "delete" | "silence" | "escalate";
      note?: string | null;
    };
    ReviewableEventResponse: {
      actor_id?: string | null;
      actor_name?: string | null;
      created_at: string;
      data: {
      [key: string]: unknown;
    };
      event: string;
      from_status?: string | null;
      id: string;
      note?: string | null;
      to_status?: string | null;
    };
    ReviewableResponse: {
      appeal_available?: boolean;
      assigned_at?: string | null;
      assigned_to_id?: string | null;
      assigned_to_name?: string | null;
      board_id?: string | null;
      board_name?: string | null;
      created_at: string;
      created_by_id?: string | null;
      created_by_name?: string | null;
      data: {
      [key: string]: unknown;
    };
      events?: Array<components["schemas"]["ReviewableEventResponse"]>;
      flag_id?: string | null;
      id: string;
      post_id?: string | null;
      priority: number;
      resolved_at?: string | null;
      resolved_by_id?: string | null;
      resolved_by_name?: string | null;
      source: string;
      source_summary: string;
      status: string;
      target_id?: string | null;
      target_type?: string | null;
      target_user_id?: string | null;
      target_user_name?: string | null;
      topic_id?: string | null;
      type: string;
      updated_at: string;
    };
    ScreenedRuleCreateRequest: {
      action?: "block" | "silence";
      kind: "email" | "ip" | "url";
      note?: string | null;
      value: string;
    };
    ScreenedRuleResponse: {
      action: string;
      active: boolean;
      created_at: string;
      created_by_id?: string | null;
      created_by_name?: string | null;
      id: string;
      kind: string;
      note?: string | null;
      updated_at: string;
      value: string;
    };
    SeoMetaResponse: {
      canonical_url: string;
      description: string;
      og_description: string;
      og_title: string;
      og_type?: string;
      og_url: string;
      robots?: string;
      title: string;
      twitter_card?: string;
    };
    SessionResponse: {
      created_at: string;
      current?: boolean;
      id: string;
      ip_address: string | null;
      last_seen_at: string;
      revoked_at?: string | null;
      user_agent: string | null;
    };
    SimilarTopicResponse: {
      board_name: string;
      board_slug: string;
      excerpt: string;
      id: string;
      matched_terms: Array<string>;
      score: number;
      slug: string;
      title: string;
    };
    SimilarTopicsRequest: {
      limit?: number;
      raw_md?: string;
      tags?: Array<string>;
      title: string;
    };
    SiteSettingResponse: {
      category: string;
      created_at: string;
      data_type: string;
      description: string;
      id: string;
      key: string;
      public: boolean;
      updated_at: string;
      updated_by_id?: string | null;
      updated_by_name?: string | null;
      value: unknown;
    };
    SiteSettingUpdateRequest: {
      value: unknown;
    };
    SpamActionResponse: {
      action: string;
      created_at: string;
      data: {
      [key: string]: unknown;
    };
      email?: string | null;
      id: string;
      ip_address?: string | null;
      kind: string;
      reason: string;
      screened_rule_id?: string | null;
      updated_at: string;
      url?: string | null;
      user_id?: string | null;
      username?: string | null;
    };
    TagResponse: {
      id: string;
      name: string;
      slug: string;
      topic_count: number;
    };
    TokenPair: {
      access_token: string;
      refresh_token: string;
      session_id?: string | null;
      token_type?: string;
      user: components["schemas"]["UserPublic"];
    };
    TopicAiSummaryResponse: {
      cost_units: number;
      generated_at: string;
      key_points: Array<string>;
      key_post_ids: Array<string>;
      model_name: string;
      refreshed_by_id?: string | null;
      summary: string;
      topic_id: string;
      updated_at: string;
    };
    TopicCreateRequest: {
      featured?: boolean;
      pinned?: boolean;
      poll?: components["schemas"]["PollCreateRequest"] | null;
      raw_md: string;
      tags?: Array<string>;
      title: string;
    };
    TopicLifecycleRequest: {
      note?: string | null;
      pinned?: boolean | null;
      status?: "open" | "closed" | "archived" | null;
    };
    TopicLifecycleResponse: {
      audit_action: string;
      moved_post_count?: number;
      source_topic?: components["schemas"]["TopicResponse"] | null;
      target_topic: components["schemas"]["TopicResponse"];
    };
    TopicLocalizationResponse: {
      available_locales?: Array<string>;
      fallback_title: string;
      fallback_used: boolean;
      locale: string;
      title: string;
      topic_id: string;
    };
    TopicLocalizationUpdateRequest: {
      title?: string | null;
    };
    TopicMergeRequest: {
      note?: string | null;
      target_topic_id: string;
    };
    TopicMoveRequest: {
      board_id?: string | null;
      board_slug?: string | null;
      note?: string | null;
    };
    TopicNotificationLevelRequest: {
      notification_level: "muted" | "normal" | "tracking" | "watching";
    };
    TopicNotificationLevelResponse: {
      last_read_post_number: number;
      notification_level: "muted" | "normal" | "tracking" | "watching";
      topic_id: string;
    };
    TopicReadStateRequest: {
      last_read_post_number?: number | null;
    };
    TopicReadStateResponse: {
      highest_post_number: number;
      last_read_post_number: number;
      notification_level: "muted" | "normal" | "tracking" | "watching";
      read: boolean;
      topic_id: string;
      unread_count: number;
    };
    TopicResponse: {
      accepted_answer_post_id?: string | null;
      answer_mode?: boolean;
      author_avatar_url?: string | null;
      author_id: string;
      author_level: number;
      author_name: string;
      author_role: string;
      author_trust_level: number;
      author_trust_level_label: string;
      board_color: string;
      board_id: string;
      board_name: string;
      board_slug: string;
      bookmark_count?: number;
      bookmarked_by_me?: boolean;
      created_at: string;
      excerpt: string;
      featured: boolean;
      hot_score: number;
      id: string;
      last_posted_at: string;
      like_count: number;
      liked_by_me?: boolean;
      merged_into_topic_id?: string | null;
      my_vote?: number;
      pinned: boolean;
      poll?: components["schemas"]["PollResponse"] | null;
      reply_count: number;
      share_url: string;
      slug: string;
      solved_at?: string | null;
      solved_by_id?: string | null;
      status: string;
      tags: Array<string>;
      title: string;
      title_localizations?: {
      [key: string]: string;
    };
      topic_type: string;
      updated_at: string;
      view_count: number;
      visibility: string;
      vote_count?: number;
      vote_score?: number;
    };
    TopicSolutionRequest: {
      post_id?: string | null;
    };
    TopicSplitRequest: {
      board_id?: string | null;
      board_slug?: string | null;
      note?: string | null;
      post_ids: Array<string>;
      title: string;
    };
    TwoFactorDisableRequest: {
      code: string;
      password: string;
    };
    TwoFactorEnableRequest: {
      code: string;
      secret: string;
    };
    TwoFactorLoginVerifyRequest: {
      challenge_token: string;
      code: string;
    };
    TwoFactorRecoveryCodesResponse: {
      recovery_codes: Array<string>;
    };
    TwoFactorSetupRequest: {
      password: string;
    };
    TwoFactorSetupResponse: {
      otpauth_url: string;
      secret: string;
    };
    UploadResponse: {
      byte_size: number;
      created_at: string;
      id: string;
      is_image: boolean;
      kind: string;
      media_type: string;
      original_filename: string;
      status: string;
      url: string;
    };
    UserActivityItemResponse: {
      created_at: string;
      excerpt: string;
      id: string;
      post_number?: number | null;
      topic_id: string;
      topic_slug: string;
      topic_title: string;
      type: "post" | "liked_topic" | "liked_post" | "bookmarked_topic" | "bookmarked_post";
    };
    UserBadgeResponse: {
      badge_id: string;
      badge_slug: string;
      category: string;
      description: string;
      granted_at: string;
      granted_by_id?: string | null;
      icon: string;
      id: string;
      name: string;
      note?: string | null;
      revoke_reason?: string | null;
      revoked_at?: string | null;
      revoked_by_id?: string | null;
      source_id?: string | null;
      source_type: string;
    };
    UserDirectoryResponse: {
      avatar_url?: string | null;
      created_at: string;
      display_name?: string | null;
      id: string;
      last_seen_at?: string | null;
      level: number;
      points_balance: number;
      post_count: number;
      role: string;
      topic_count: number;
      trust_level: number;
      trust_level_label: string;
      username: string;
    };
    UserProfileResponse: {
      avatar_url?: string | null;
      badges?: Array<components["schemas"]["UserBadgeResponse"]>;
      bio?: string | null;
      can_edit?: boolean;
      created_at: string;
      display_name?: string | null;
      experience_to_next_level: number;
      experience_total: number;
      follower_count: number;
      following_count: number;
      id: string;
      level: number;
      level_progress_percent: number;
      location?: string | null;
      points_balance: number;
      post_count: number;
      profile_visibility: string;
      role: string;
      show_activity: boolean;
      status: string;
      topic_count: number;
      trust_level: number;
      trust_level_label: string;
      username: string;
      website_url?: string | null;
    };
    UserProfileUpdateRequest: {
      bio?: string | null;
      display_name?: string | null;
      interface_theme?: "system" | "light" | "colorful" | null;
      locale?: "zh-CN" | "en-US" | null;
      location?: string | null;
      profile_visibility?: "public" | "members" | "private" | null;
      show_activity?: boolean | null;
      website_url?: string | null;
    };
    UserPublic: {
      avatar_url?: string | null;
      bio?: string | null;
      created_at: string;
      display_name?: string | null;
      email: string;
      experience_to_next_level: number;
      experience_total: number;
      id: string;
      interface_theme: string;
      level: number;
      level_progress_percent: number;
      locale: string;
      location?: string | null;
      points_balance: number;
      profile_visibility: string;
      role: string;
      show_activity: boolean;
      status: string;
      trust_level: number;
      trust_level_label: string;
      two_factor_enabled: boolean;
      username: string;
      website_url?: string | null;
    };
    UserRelationshipStateResponse: {
      blocked: boolean;
      followed_by: boolean;
      following: boolean;
      ignored: boolean;
      target_user_id: string;
      target_username: string;
    };
    UserRelationshipUserResponse: {
      avatar_url?: string | null;
      display_name?: string | null;
      followed_at: string;
      id: string;
      level: number;
      post_count: number;
      role: string;
      topic_count: number;
      trust_level: number;
      trust_level_label: string;
      username: string;
    };
    UserStatusResponse: {
      status: string;
      user_id: string;
      username: string;
    };
    UserStatusUpdateRequest: {
      note?: string | null;
      status: "active" | "silenced" | "suspended";
    };
    ValidationError: {
      ctx?: Record<string, unknown>;
      input?: unknown;
      loc: Array<string | number>;
      msg: string;
      type: string;
    };
    VerifyEmailRequest: {
      code: string;
      email: string;
    };
    VoteRequest: {
      value?: -1 | 0 | 1;
    };
    VoteStateResponse: {
      count: number;
      score: number;
      target_id: string;
      target_type: "post" | "topic";
      value: number;
    };
    WebhookDeliveryResponse: {
      attempt_count: number;
      created_at: string;
      delivered_at?: string | null;
      endpoint_id: string;
      endpoint_name?: string | null;
      event_type: string;
      id: string;
      last_error?: string | null;
      last_status_code?: number | null;
      max_attempts: number;
      next_attempt_at?: string | null;
      response_body_excerpt?: string | null;
      status: "pending" | "retrying" | "succeeded" | "failed" | "disabled" | string;
      updated_at: string;
    };
    WebhookEndpointCreateRequest: {
      events?: Array<string>;
      name: string;
      note?: string | null;
      url: string;
    };
    WebhookEndpointCreateResponse: {
      secret: string;
      webhook: components["schemas"]["WebhookEndpointResponse"];
    };
    WebhookEndpointResponse: {
      active: boolean;
      created_at: string;
      created_by_id?: string | null;
      disabled_at?: string | null;
      disabled_by_id?: string | null;
      events: Array<string>;
      id: string;
      name: string;
      note?: string | null;
      updated_at: string;
      url: string;
    };
  };
}

export interface paths {
    "/api/v1/admin/analytics": {
      get: { response: components["schemas"]["ApiResponse_AnalyticsOverviewResponse_"]; operationId: "analytics_overview_api_v1_admin_analytics_get" };
    };
    "/api/v1/admin/analytics/reports": {
      get: { response: components["schemas"]["ApiResponse_list_DataExplorerReportSummary__"]; operationId: "list_data_explorer_reports_api_v1_admin_analytics_reports_get" };
    };
    "/api/v1/admin/analytics/reports/{report_id}": {
      get: { response: components["schemas"]["ApiResponse_DataExplorerReportResponse_"]; operationId: "run_data_explorer_report_api_v1_admin_analytics_reports__report_id__get" };
    };
    "/api/v1/admin/analytics/reports/{report_id}/export.csv": {
      get: { response: unknown; operationId: "export_data_explorer_report_api_v1_admin_analytics_reports__report_id__export_csv_get" };
    };
    "/api/v1/admin/api-keys": {
      get: { response: components["schemas"]["ApiResponse_list_ApiKeyResponse__"]; operationId: "list_api_keys_api_v1_admin_api_keys_get" };
      post: { response: components["schemas"]["ApiResponse_ApiKeyCreateResponse_"]; operationId: "create_api_key_api_v1_admin_api_keys_post" };
    };
    "/api/v1/admin/api-keys/{key_id}/disable": {
      post: { response: components["schemas"]["ApiResponse_ApiKeyResponse_"]; operationId: "disable_api_key_api_v1_admin_api_keys__key_id__disable_post" };
    };
    "/api/v1/admin/audit-logs": {
      get: { response: components["schemas"]["ApiResponse_list_AuditLogResponse__"]; operationId: "list_audit_logs_api_v1_admin_audit_logs_get" };
    };
    "/api/v1/admin/background-jobs": {
      get: { response: components["schemas"]["ApiResponse_list_AdminBackgroundJobResponse__"]; operationId: "list_background_jobs_api_v1_admin_background_jobs_get" };
    };
    "/api/v1/admin/background-jobs/{job_id}/logs": {
      get: { response: components["schemas"]["ApiResponse_list_AdminBackgroundJobLogResponse__"]; operationId: "list_background_job_logs_api_v1_admin_background_jobs__job_id__logs_get" };
    };
    "/api/v1/admin/backups": {
      get: { response: components["schemas"]["ApiResponse_list_BackupArtifactResponse__"]; operationId: "list_backups_api_v1_admin_backups_get" };
      post: { response: components["schemas"]["ApiResponse_BackupArtifactResponse_"]; operationId: "create_backup_api_v1_admin_backups_post" };
    };
    "/api/v1/admin/backups/{backup_id}": {
      delete: { response: components["schemas"]["ApiResponse_BackupArtifactResponse_"]; operationId: "delete_backup_api_v1_admin_backups__backup_id__delete" };
      get: { response: components["schemas"]["ApiResponse_BackupArtifactResponse_"]; operationId: "get_backup_api_v1_admin_backups__backup_id__get" };
    };
    "/api/v1/admin/backups/{backup_id}/download": {
      get: { response: unknown; operationId: "download_backup_api_v1_admin_backups__backup_id__download_get" };
    };
    "/api/v1/admin/backups/{backup_id}/restore": {
      post: { response: components["schemas"]["ApiResponse_BackupRestoreResponse_"]; operationId: "validate_backup_restore_api_v1_admin_backups__backup_id__restore_post" };
    };
    "/api/v1/admin/badges": {
      get: { response: components["schemas"]["ApiResponse_list_BadgeResponse__"]; operationId: "list_badges_api_v1_admin_badges_get" };
    };
    "/api/v1/admin/email-logs": {
      get: { response: components["schemas"]["ApiResponse_list_AdminEmailLogResponse__"]; operationId: "list_email_logs_api_v1_admin_email_logs_get" };
    };
    "/api/v1/admin/exports/site": {
      get: { response: unknown; operationId: "export_site_api_v1_admin_exports_site_get" };
    };
    "/api/v1/admin/external-integrations": {
      get: { response: components["schemas"]["ApiResponse_list_ExternalIntegrationResponse__"]; operationId: "list_external_integrations_api_v1_admin_external_integrations_get" };
    };
    "/api/v1/admin/external-integrations/{provider}": {
      put: { response: components["schemas"]["ApiResponse_ExternalIntegrationResponse_"]; operationId: "update_external_integration_api_v1_admin_external_integrations__provider__put" };
    };
    "/api/v1/admin/external-integrations/events": {
      get: { response: components["schemas"]["ApiResponse_list_ExternalIntegrationEventResponse__"]; operationId: "list_external_integration_events_api_v1_admin_external_integrations_events_get" };
    };
    "/api/v1/admin/external-integrations/events/{event_id}/retry": {
      post: { response: components["schemas"]["ApiResponse_ExternalIntegrationEventResponse_"]; operationId: "retry_external_integration_event_api_v1_admin_external_integrations_events__event_id__retry_post" };
    };
    "/api/v1/admin/frontier-news/collect": {
      post: { response: components["schemas"]["ApiResponse_FrontierNewsCollectResponse_"]; operationId: "collect_all_frontier_news_api_v1_admin_frontier_news_collect_post" };
    };
    "/api/v1/admin/frontier-news/items": {
      get: { response: components["schemas"]["ApiResponse_list_FrontierNewsItemResponse__"]; operationId: "list_frontier_news_items_api_v1_admin_frontier_news_items_get" };
    };
    "/api/v1/admin/frontier-news/items/{item_id}/enrich": {
      post: { response: components["schemas"]["ApiResponse_FrontierNewsItemResponse_"]; operationId: "enrich_frontier_news_item_api_v1_admin_frontier_news_items__item_id__enrich_post" };
    };
    "/api/v1/admin/frontier-news/items/{item_id}/queue": {
      post: { response: components["schemas"]["ApiResponse_FrontierNewsItemResponse_"]; operationId: "queue_frontier_news_item_api_v1_admin_frontier_news_items__item_id__queue_post" };
    };
    "/api/v1/admin/frontier-news/sources": {
      get: { response: components["schemas"]["ApiResponse_list_FrontierNewsSourceResponse__"]; operationId: "list_frontier_news_sources_api_v1_admin_frontier_news_sources_get" };
      post: { response: components["schemas"]["ApiResponse_FrontierNewsSourceResponse_"]; operationId: "create_frontier_news_source_api_v1_admin_frontier_news_sources_post" };
    };
    "/api/v1/admin/frontier-news/sources/{source_id}": {
      put: { response: components["schemas"]["ApiResponse_FrontierNewsSourceResponse_"]; operationId: "update_frontier_news_source_api_v1_admin_frontier_news_sources__source_id__put" };
    };
    "/api/v1/admin/frontier-news/sources/{source_id}/collect": {
      post: { response: components["schemas"]["ApiResponse_FrontierNewsCollectResponse_"]; operationId: "collect_frontier_news_source_api_v1_admin_frontier_news_sources__source_id__collect_post" };
    };
    "/api/v1/admin/migrations/export": {
      get: { response: components["schemas"]["ApiResponse_MigrationExportResponse_"]; operationId: "export_migration_json_api_v1_admin_migrations_export_get" };
    };
    "/api/v1/admin/migrations/import/preview": {
      post: { response: components["schemas"]["ApiResponse_MigrationImportResponse_"]; operationId: "preview_migration_import_api_v1_admin_migrations_import_preview_post" };
    };
    "/api/v1/admin/migrations/import/run": {
      post: { response: components["schemas"]["ApiResponse_MigrationImportResponse_"]; operationId: "run_migration_import_api_v1_admin_migrations_import_run_post" };
    };
    "/api/v1/admin/plugins": {
      get: { response: components["schemas"]["ApiResponse_list_PluginResponse__"]; operationId: "list_plugins_api_v1_admin_plugins_get" };
    };
    "/api/v1/admin/plugins/{plugin_id}": {
      put: { response: components["schemas"]["ApiResponse_PluginResponse_"]; operationId: "update_plugin_api_v1_admin_plugins__plugin_id__put" };
    };
    "/api/v1/admin/settings": {
      get: { response: components["schemas"]["ApiResponse_list_SiteSettingResponse__"]; operationId: "list_site_settings_api_v1_admin_settings_get" };
    };
    "/api/v1/admin/settings/{key}": {
      put: { response: components["schemas"]["ApiResponse_SiteSettingResponse_"]; operationId: "update_site_setting_api_v1_admin_settings__key__put" };
    };
    "/api/v1/admin/system": {
      get: { response: components["schemas"]["ApiResponse_AdminSystemOverviewResponse_"]; operationId: "system_overview_api_v1_admin_system_get" };
    };
    "/api/v1/admin/users": {
      get: { response: components["schemas"]["ApiResponse_list_AdminUserResponse__"]; operationId: "list_users_api_v1_admin_users_get" };
    };
    "/api/v1/admin/users/{user_id}": {
      delete: { response: components["schemas"]["ApiResponse_PrivacyActionResponse_"]; operationId: "delete_user_account_api_v1_admin_users__user_id__delete" };
      get: { response: components["schemas"]["ApiResponse_AdminUserResponse_"]; operationId: "get_user_api_v1_admin_users__user_id__get" };
      put: { response: components["schemas"]["ApiResponse_AdminUserResponse_"]; operationId: "update_user_api_v1_admin_users__user_id__put" };
    };
    "/api/v1/admin/users/{user_id}/anonymize": {
      post: { response: components["schemas"]["ApiResponse_PrivacyActionResponse_"]; operationId: "anonymize_user_api_v1_admin_users__user_id__anonymize_post" };
    };
    "/api/v1/admin/users/{user_id}/badges": {
      post: { response: components["schemas"]["ApiResponse_AdminUserResponse_"]; operationId: "grant_user_badge_api_v1_admin_users__user_id__badges_post" };
    };
    "/api/v1/admin/users/{user_id}/badges/{badge_slug}/revoke": {
      post: { response: components["schemas"]["ApiResponse_AdminUserResponse_"]; operationId: "revoke_user_badge_api_v1_admin_users__user_id__badges__badge_slug__revoke_post" };
    };
    "/api/v1/admin/webhook-deliveries": {
      get: { response: components["schemas"]["ApiResponse_list_WebhookDeliveryResponse__"]; operationId: "list_webhook_deliveries_api_v1_admin_webhook_deliveries_get" };
    };
    "/api/v1/admin/webhooks": {
      get: { response: components["schemas"]["ApiResponse_list_WebhookEndpointResponse__"]; operationId: "list_webhooks_api_v1_admin_webhooks_get" };
      post: { response: components["schemas"]["ApiResponse_WebhookEndpointCreateResponse_"]; operationId: "create_webhook_api_v1_admin_webhooks_post" };
    };
    "/api/v1/admin/webhooks/{webhook_id}/disable": {
      post: { response: components["schemas"]["ApiResponse_WebhookEndpointResponse_"]; operationId: "disable_webhook_api_v1_admin_webhooks__webhook_id__disable_post" };
    };
    "/api/v1/ai/moderation-advice": {
      post: { response: components["schemas"]["ApiResponse_ModerationAdviceResponse_"]; operationId: "moderation_ai_advice_api_v1_ai_moderation_advice_post" };
    };
    "/api/v1/ai/similar-topics": {
      post: { response: components["schemas"]["ApiResponse_list_SimilarTopicResponse__"]; operationId: "suggest_similar_topics_api_v1_ai_similar_topics_post" };
    };
    "/api/v1/auth/2fa/disable": {
      post: { response: components["schemas"]["ApiResponse_dict_str__bool__"]; operationId: "disable_two_factor_api_v1_auth_2fa_disable_post" };
    };
    "/api/v1/auth/2fa/enable": {
      post: { response: components["schemas"]["ApiResponse_TwoFactorRecoveryCodesResponse_"]; operationId: "enable_two_factor_api_v1_auth_2fa_enable_post" };
    };
    "/api/v1/auth/2fa/recovery-codes": {
      post: { response: components["schemas"]["ApiResponse_TwoFactorRecoveryCodesResponse_"]; operationId: "regenerate_recovery_codes_api_v1_auth_2fa_recovery_codes_post" };
    };
    "/api/v1/auth/2fa/setup": {
      post: { response: components["schemas"]["ApiResponse_TwoFactorSetupResponse_"]; operationId: "setup_two_factor_api_v1_auth_2fa_setup_post" };
    };
    "/api/v1/auth/2fa/verify-login": {
      post: { response: components["schemas"]["ApiResponse_TokenPair_"]; operationId: "verify_two_factor_login_api_v1_auth_2fa_verify_login_post" };
    };
    "/api/v1/auth/email-change/confirm": {
      post: { response: components["schemas"]["ApiResponse_UserPublic_"]; operationId: "confirm_email_change_api_v1_auth_email_change_confirm_post" };
    };
    "/api/v1/auth/email-change/request": {
      post: { response: components["schemas"]["ApiResponse_EmailChangeStartResponse_"]; operationId: "request_email_change_api_v1_auth_email_change_request_post" };
    };
    "/api/v1/auth/login": {
      post: { response: components["schemas"]["ApiResponse_LoginResponse_"]; operationId: "login_api_v1_auth_login_post" };
    };
    "/api/v1/auth/logout": {
      post: { response: components["schemas"]["ApiResponse_dict_str__bool__"]; operationId: "logout_api_v1_auth_logout_post" };
    };
    "/api/v1/auth/me": {
      get: { response: components["schemas"]["ApiResponse_UserPublic_"]; operationId: "me_api_v1_auth_me_get" };
    };
    "/api/v1/auth/oauth/providers": {
      get: { response: components["schemas"]["ApiResponse_OAuthProviderResponse_"]; operationId: "oauth_providers_api_v1_auth_oauth_providers_get" };
    };
    "/api/v1/auth/password-reset/confirm": {
      post: { response: components["schemas"]["ApiResponse_dict_str__bool__"]; operationId: "confirm_password_reset_api_v1_auth_password_reset_confirm_post" };
    };
    "/api/v1/auth/password-reset/request": {
      post: { response: components["schemas"]["ApiResponse_PasswordResetStartResponse_"]; operationId: "request_password_reset_api_v1_auth_password_reset_request_post" };
    };
    "/api/v1/auth/password/change": {
      post: { response: components["schemas"]["ApiResponse_dict_str__bool__"]; operationId: "change_password_api_v1_auth_password_change_post" };
    };
    "/api/v1/auth/refresh": {
      post: { response: components["schemas"]["ApiResponse_dict_str__str__"]; operationId: "refresh_api_v1_auth_refresh_post" };
    };
    "/api/v1/auth/register": {
      post: { response: components["schemas"]["ApiResponse_RegistrationStartResponse_"]; operationId: "register_api_v1_auth_register_post" };
    };
    "/api/v1/auth/resend-verification": {
      post: { response: components["schemas"]["ApiResponse_RegistrationStartResponse_"]; operationId: "resend_verification_api_v1_auth_resend_verification_post" };
    };
    "/api/v1/auth/sessions": {
      get: { response: components["schemas"]["ApiResponse_list_SessionResponse__"]; operationId: "list_sessions_api_v1_auth_sessions_get" };
    };
    "/api/v1/auth/sessions/{session_id}": {
      delete: { response: components["schemas"]["ApiResponse_dict_str__bool__"]; operationId: "revoke_session_api_v1_auth_sessions__session_id__delete" };
    };
    "/api/v1/auth/sessions/revoke-others": {
      post: { response: components["schemas"]["ApiResponse_dict_str__int__"]; operationId: "revoke_other_sessions_api_v1_auth_sessions_revoke_others_post" };
    };
    "/api/v1/auth/verify-email": {
      post: { response: components["schemas"]["ApiResponse_TokenPair_"]; operationId: "verify_email_api_v1_auth_verify_email_post" };
    };
    "/api/v1/boards": {
      get: { response: components["schemas"]["ApiResponse_list_BoardResponse__"]; operationId: "list_boards_api_v1_boards_get" };
      post: { response: components["schemas"]["ApiResponse_BoardResponse_"]; operationId: "create_board_api_v1_boards_post" };
    };
    "/api/v1/boards/{slug}": {
      get: { response: components["schemas"]["ApiResponse_BoardDetailResponse_"]; operationId: "get_board_api_v1_boards__slug__get" };
    };
    "/api/v1/boards/{slug}/follow": {
      delete: { response: components["schemas"]["ApiResponse_BoardFollowResponse_"]; operationId: "unfollow_board_api_v1_boards__slug__follow_delete" };
      put: { response: components["schemas"]["ApiResponse_BoardFollowResponse_"]; operationId: "follow_board_api_v1_boards__slug__follow_put" };
    };
    "/api/v1/boards/{slug}/members/{username}": {
      delete: { response: components["schemas"]["ApiResponse_BoardMemberRemoveResponse_"]; operationId: "remove_board_member_api_v1_boards__slug__members__username__delete" };
      put: { response: components["schemas"]["ApiResponse_BoardMemberResponse_"]; operationId: "update_board_member_api_v1_boards__slug__members__username__put" };
    };
    "/api/v1/boards/{slug}/settings": {
      get: { response: components["schemas"]["ApiResponse_BoardSettingsResponse_"]; operationId: "get_board_settings_api_v1_boards__slug__settings_get" };
      put: { response: components["schemas"]["ApiResponse_BoardResponse_"]; operationId: "update_board_settings_api_v1_boards__slug__settings_put" };
    };
    "/api/v1/boards/{slug}/topics": {
      get: { response: components["schemas"]["ApiResponse_list_TopicResponse__"]; operationId: "list_board_topics_api_v1_boards__slug__topics_get" };
      post: { response: components["schemas"]["ApiResponse_TopicResponse_"]; operationId: "create_topic_api_v1_boards__slug__topics_post" };
    };
    "/api/v1/docs/public": {
      get: { response: components["schemas"]["ApiResponse_PublicApiDocsResponse_"]; operationId: "public_api_docs_api_v1_docs_public_get" };
    };
    "/api/v1/drafts": {
      delete: { response: components["schemas"]["ApiResponse_bool_"]; operationId: "delete_draft_api_v1_drafts_delete" };
      get: { response: components["schemas"]["ApiResponse_list_DraftResponse__"]; operationId: "list_drafts_api_v1_drafts_get" };
      put: { response: components["schemas"]["ApiResponse_DraftResponse_"]; operationId: "save_draft_api_v1_drafts_put" };
    };
    "/api/v1/drafts/lookup": {
      get: { response: components["schemas"]["ApiResponse_Union_DraftResponse__NoneType__"]; operationId: "lookup_draft_api_v1_drafts_lookup_get" };
    };
    "/api/v1/email/preferences": {
      get: { response: components["schemas"]["ApiResponse_EmailPreferenceResponse_"]; operationId: "get_email_preferences_api_v1_email_preferences_get" };
      put: { response: components["schemas"]["ApiResponse_EmailPreferenceResponse_"]; operationId: "update_email_preferences_api_v1_email_preferences_put" };
    };
    "/api/v1/email/webhooks/delivery": {
      post: { response: components["schemas"]["ApiResponse_EmailDeliveryEventResponse_"]; operationId: "record_delivery_webhook_api_v1_email_webhooks_delivery_post" };
    };
    "/api/v1/email/webhooks/inbound-reply": {
      post: { response: components["schemas"]["ApiResponse_InboundEmailResponse_"]; operationId: "record_inbound_reply_webhook_api_v1_email_webhooks_inbound_reply_post" };
    };
    "/api/v1/events": {
      get: { response: components["schemas"]["ApiResponse_list_EventResponse__"]; operationId: "list_events_api_v1_events_get" };
      post: { response: components["schemas"]["ApiResponse_EventResponse_"]; operationId: "create_event_api_v1_events_post" };
    };
    "/api/v1/events/{event_id}": {
      delete: { response: components["schemas"]["ApiResponse_EventResponse_"]; operationId: "delete_event_api_v1_events__event_id__delete" };
    };
    "/api/v1/events/{event_id}/lifecycle": {
      put: { response: components["schemas"]["ApiResponse_EventResponse_"]; operationId: "update_event_lifecycle_api_v1_events__event_id__lifecycle_put" };
    };
    "/api/v1/events/{event_id}/rsvp": {
      put: { response: components["schemas"]["ApiResponse_EventRsvpResponse_"]; operationId: "rsvp_event_api_v1_events__event_id__rsvp_put" };
    };
    "/api/v1/events/calendar.ics": {
      get: { response: unknown; operationId: "calendar_ics_api_v1_events_calendar_ics_get" };
    };
    "/api/v1/healthz": {
      get: { response: components["schemas"]["ApiResponse_dict_str__str__"]; operationId: "healthz_api_v1_healthz_get" };
    };
    "/api/v1/integrations/{provider}/webhook": {
      post: { response: components["schemas"]["ApiResponse_ExternalWebhookResponse_"]; operationId: "external_provider_webhook_api_v1_integrations__provider__webhook_post" };
    };
    "/api/v1/integrations/github/issue": {
      get: { response: components["schemas"]["ApiResponse_GitHubIssuePreviewResponse_"]; operationId: "github_issue_preview_api_v1_integrations_github_issue_get" };
    };
    "/api/v1/integrations/me": {
      get: { response: components["schemas"]["ApiResponse_ApiKeyResponse_"]; operationId: "api_key_me_api_v1_integrations_me_get" };
    };
    "/api/v1/invites": {
      get: { response: components["schemas"]["ApiResponse_MyBoardInvitesResponse_"]; operationId: "list_my_invites_api_v1_invites_get" };
      post: { response: components["schemas"]["ApiResponse_BoardInviteResponse_"]; operationId: "create_invite_api_v1_invites_post" };
    };
    "/api/v1/invites/{invite_id}/accept": {
      put: { response: components["schemas"]["ApiResponse_BoardInviteResponse_"]; operationId: "accept_invite_api_v1_invites__invite_id__accept_put" };
    };
    "/api/v1/invites/{invite_id}/decline": {
      put: { response: components["schemas"]["ApiResponse_BoardInviteResponse_"]; operationId: "decline_invite_api_v1_invites__invite_id__decline_put" };
    };
    "/api/v1/invites/{invite_id}/revoke": {
      put: { response: components["schemas"]["ApiResponse_BoardInviteResponse_"]; operationId: "revoke_invite_api_v1_invites__invite_id__revoke_put" };
    };
    "/api/v1/moderation/audit-logs": {
      get: { response: components["schemas"]["ApiResponse_list_AuditLogResponse__"]; operationId: "list_audit_logs_api_v1_moderation_audit_logs_get" };
    };
    "/api/v1/moderation/flags": {
      post: { response: components["schemas"]["ApiResponse_FlagResponse_"]; operationId: "create_flag_api_v1_moderation_flags_post" };
    };
    "/api/v1/moderation/flags/{flag_id}/status": {
      put: { response: components["schemas"]["ApiResponse_FlagResponse_"]; operationId: "update_flag_status_api_v1_moderation_flags__flag_id__status_put" };
    };
    "/api/v1/moderation/posts/{post_id}/delete": {
      put: { response: components["schemas"]["ApiResponse_ModerationActionResponse_"]; operationId: "delete_post_api_v1_moderation_posts__post_id__delete_put" };
    };
    "/api/v1/moderation/posts/{post_id}/hide": {
      put: { response: components["schemas"]["ApiResponse_ModerationActionResponse_"]; operationId: "hide_post_api_v1_moderation_posts__post_id__hide_put" };
    };
    "/api/v1/moderation/posts/{post_id}/restore": {
      put: { response: components["schemas"]["ApiResponse_ModerationActionResponse_"]; operationId: "restore_post_api_v1_moderation_posts__post_id__restore_put" };
    };
    "/api/v1/moderation/queue": {
      get: { response: components["schemas"]["ApiResponse_list_FlagResponse__"]; operationId: "list_moderation_queue_api_v1_moderation_queue_get" };
    };
    "/api/v1/moderation/reviewables": {
      get: { response: components["schemas"]["ApiResponse_list_ReviewableResponse__"]; operationId: "list_reviewables_api_v1_moderation_reviewables_get" };
    };
    "/api/v1/moderation/reviewables/{reviewable_id}/appeal": {
      post: { response: components["schemas"]["ApiResponse_ReviewableResponse_"]; operationId: "appeal_reviewable_api_v1_moderation_reviewables__reviewable_id__appeal_post" };
    };
    "/api/v1/moderation/reviewables/{reviewable_id}/claim": {
      post: { response: components["schemas"]["ApiResponse_ReviewableResponse_"]; operationId: "claim_reviewable_api_v1_moderation_reviewables__reviewable_id__claim_post" };
    };
    "/api/v1/moderation/reviewables/{reviewable_id}/decide": {
      post: { response: components["schemas"]["ApiResponse_ReviewableResponse_"]; operationId: "decide_reviewable_api_v1_moderation_reviewables__reviewable_id__decide_post" };
    };
    "/api/v1/moderation/reviewables/{reviewable_id}/release": {
      post: { response: components["schemas"]["ApiResponse_ReviewableResponse_"]; operationId: "release_reviewable_api_v1_moderation_reviewables__reviewable_id__release_post" };
    };
    "/api/v1/moderation/reviewables/bulk-decide": {
      post: { response: components["schemas"]["ApiResponse_ReviewableBulkDecisionResponse_"]; operationId: "decide_reviewables_bulk_api_v1_moderation_reviewables_bulk_decide_post" };
    };
    "/api/v1/moderation/reviewables/me": {
      get: { response: components["schemas"]["ApiResponse_list_ReviewableResponse__"]; operationId: "list_my_reviewables_api_v1_moderation_reviewables_me_get" };
    };
    "/api/v1/moderation/screened-rules": {
      get: { response: components["schemas"]["ApiResponse_list_ScreenedRuleResponse__"]; operationId: "list_screened_rules_api_v1_moderation_screened_rules_get" };
      post: { response: components["schemas"]["ApiResponse_ScreenedRuleResponse_"]; operationId: "create_screened_rule_api_v1_moderation_screened_rules_post" };
    };
    "/api/v1/moderation/screened-rules/{rule_id}": {
      delete: { response: components["schemas"]["ApiResponse_dict_str__bool__"]; operationId: "delete_screened_rule_api_v1_moderation_screened_rules__rule_id__delete" };
    };
    "/api/v1/moderation/spam-actions": {
      get: { response: components["schemas"]["ApiResponse_list_SpamActionResponse__"]; operationId: "list_spam_actions_api_v1_moderation_spam_actions_get" };
    };
    "/api/v1/moderation/topics/{topic_id}/delete": {
      put: { response: components["schemas"]["ApiResponse_ModerationActionResponse_"]; operationId: "delete_topic_api_v1_moderation_topics__topic_id__delete_put" };
    };
    "/api/v1/moderation/topics/{topic_id}/hide": {
      put: { response: components["schemas"]["ApiResponse_ModerationActionResponse_"]; operationId: "hide_topic_api_v1_moderation_topics__topic_id__hide_put" };
    };
    "/api/v1/moderation/topics/{topic_id}/restore": {
      put: { response: components["schemas"]["ApiResponse_ModerationActionResponse_"]; operationId: "restore_topic_api_v1_moderation_topics__topic_id__restore_put" };
    };
    "/api/v1/moderation/users/{user_id}/status": {
      put: { response: components["schemas"]["ApiResponse_UserStatusResponse_"]; operationId: "update_user_status_api_v1_moderation_users__user_id__status_put" };
    };
    "/api/v1/notifications": {
      get: { response: components["schemas"]["ApiResponse_NotificationListResponse_"]; operationId: "list_notifications_api_v1_notifications_get" };
    };
    "/api/v1/notifications/push-subscription": {
      delete: { response: components["schemas"]["ApiResponse_PushSubscriptionStateResponse_"]; operationId: "delete_push_subscription_api_v1_notifications_push_subscription_delete" };
      get: { response: components["schemas"]["ApiResponse_PushSubscriptionStateResponse_"]; operationId: "get_push_subscription_api_v1_notifications_push_subscription_get" };
      post: { response: components["schemas"]["ApiResponse_PushSubscriptionStateResponse_"]; operationId: "save_push_subscription_api_v1_notifications_push_subscription_post" };
    };
    "/api/v1/notifications/read": {
      put: { response: components["schemas"]["ApiResponse_NotificationReadResponse_"]; operationId: "mark_notifications_read_api_v1_notifications_read_put" };
    };
    "/api/v1/notifications/stream": {
      get: { response: unknown; operationId: "stream_notifications_api_v1_notifications_stream_get" };
    };
    "/api/v1/posts/{post_id}": {
      delete: { response: components["schemas"]["ApiResponse_PostResponse_"]; operationId: "delete_post_api_v1_posts__post_id__delete" };
      patch: { response: components["schemas"]["ApiResponse_PostResponse_"]; operationId: "update_post_api_v1_posts__post_id__patch" };
    };
    "/api/v1/posts/{post_id}/like": {
      delete: { response: components["schemas"]["ApiResponse_InteractionStateResponse_"]; operationId: "unlike_post_api_v1_posts__post_id__like_delete" };
      put: { response: components["schemas"]["ApiResponse_InteractionStateResponse_"]; operationId: "like_post_api_v1_posts__post_id__like_put" };
    };
    "/api/v1/posts/{post_id}/revisions": {
      get: { response: components["schemas"]["ApiResponse_list_PostRevisionResponse__"]; operationId: "list_post_revisions_api_v1_posts__post_id__revisions_get" };
    };
    "/api/v1/posts/{post_id}/revisions/{revision_id}": {
      get: { response: components["schemas"]["ApiResponse_PostRevisionResponse_"]; operationId: "get_post_revision_api_v1_posts__post_id__revisions__revision_id__get" };
    };
    "/api/v1/posts/{post_id}/revisions/{revision_id}/restore": {
      post: { response: components["schemas"]["ApiResponse_PostResponse_"]; operationId: "restore_post_revision_api_v1_posts__post_id__revisions__revision_id__restore_post" };
    };
    "/api/v1/posts/{post_id}/vote": {
      put: { response: components["schemas"]["ApiResponse_VoteStateResponse_"]; operationId: "vote_post_api_v1_posts__post_id__vote_put" };
    };
    "/api/v1/search": {
      get: { response: components["schemas"]["ApiResponse_list_TopicResponse__"]; operationId: "search_topics_api_v1_search_get" };
    };
    "/api/v1/seo/meta": {
      get: { response: components["schemas"]["ApiResponse_SeoMetaResponse_"]; operationId: "seo_meta_api_v1_seo_meta_get" };
    };
    "/api/v1/site/extensions": {
      get: { response: components["schemas"]["ApiResponse_list_PluginUiExtensionResponse__"]; operationId: "public_site_extensions_api_v1_site_extensions_get" };
    };
    "/api/v1/site/settings": {
      get: { response: components["schemas"]["ApiResponse_PublicSiteSettingsResponse_"]; operationId: "public_site_settings_api_v1_site_settings_get" };
    };
    "/api/v1/tags": {
      get: { response: components["schemas"]["ApiResponse_list_TagResponse__"]; operationId: "list_tags_api_v1_tags_get" };
    };
    "/api/v1/topics": {
      get: { response: components["schemas"]["ApiResponse_list_TopicResponse__"]; operationId: "list_topics_api_v1_topics_get" };
    };
    "/api/v1/topics/{topic_id}": {
      get: { response: components["schemas"]["ApiResponse_TopicResponse_"]; operationId: "get_topic_api_v1_topics__topic_id__get" };
    };
    "/api/v1/topics/{topic_id}/ai-summary": {
      get: { response: components["schemas"]["ApiResponse_TopicAiSummaryResponse_"]; operationId: "get_topic_ai_summary_api_v1_topics__topic_id__ai_summary_get" };
    };
    "/api/v1/topics/{topic_id}/ai-summary/refresh": {
      post: { response: components["schemas"]["ApiResponse_TopicAiSummaryResponse_"]; operationId: "refresh_topic_ai_summary_api_v1_topics__topic_id__ai_summary_refresh_post" };
    };
    "/api/v1/topics/{topic_id}/bookmark": {
      delete: { response: components["schemas"]["ApiResponse_InteractionStateResponse_"]; operationId: "unbookmark_topic_api_v1_topics__topic_id__bookmark_delete" };
      put: { response: components["schemas"]["ApiResponse_InteractionStateResponse_"]; operationId: "bookmark_topic_api_v1_topics__topic_id__bookmark_put" };
    };
    "/api/v1/topics/{topic_id}/lifecycle": {
      put: { response: components["schemas"]["ApiResponse_TopicResponse_"]; operationId: "update_topic_lifecycle_api_v1_topics__topic_id__lifecycle_put" };
    };
    "/api/v1/topics/{topic_id}/like": {
      delete: { response: components["schemas"]["ApiResponse_InteractionStateResponse_"]; operationId: "unlike_topic_api_v1_topics__topic_id__like_delete" };
      put: { response: components["schemas"]["ApiResponse_InteractionStateResponse_"]; operationId: "like_topic_api_v1_topics__topic_id__like_put" };
    };
    "/api/v1/topics/{topic_id}/localizations/{locale}": {
      get: { response: components["schemas"]["ApiResponse_TopicLocalizationResponse_"]; operationId: "get_topic_localization_api_v1_topics__topic_id__localizations__locale__get" };
      put: { response: components["schemas"]["ApiResponse_TopicLocalizationResponse_"]; operationId: "update_topic_localization_api_v1_topics__topic_id__localizations__locale__put" };
    };
    "/api/v1/topics/{topic_id}/merge": {
      post: { response: components["schemas"]["ApiResponse_TopicLifecycleResponse_"]; operationId: "merge_topic_api_v1_topics__topic_id__merge_post" };
    };
    "/api/v1/topics/{topic_id}/move": {
      post: { response: components["schemas"]["ApiResponse_TopicResponse_"]; operationId: "move_topic_api_v1_topics__topic_id__move_post" };
    };
    "/api/v1/topics/{topic_id}/notification-level": {
      get: { response: components["schemas"]["ApiResponse_TopicNotificationLevelResponse_"]; operationId: "get_topic_notification_level_api_v1_topics__topic_id__notification_level_get" };
      put: { response: components["schemas"]["ApiResponse_TopicNotificationLevelResponse_"]; operationId: "set_topic_notification_level_api_v1_topics__topic_id__notification_level_put" };
    };
    "/api/v1/topics/{topic_id}/poll": {
      get: { response: components["schemas"]["ApiResponse_PollResponse_"]; operationId: "get_topic_poll_api_v1_topics__topic_id__poll_get" };
    };
    "/api/v1/topics/{topic_id}/poll/vote": {
      put: { response: components["schemas"]["ApiResponse_PollResponse_"]; operationId: "vote_topic_poll_api_v1_topics__topic_id__poll_vote_put" };
    };
    "/api/v1/topics/{topic_id}/posts": {
      get: { response: components["schemas"]["ApiResponse_list_PostResponse__"]; operationId: "list_posts_api_v1_topics__topic_id__posts_get" };
      post: { response: components["schemas"]["ApiResponse_PostResponse_"]; operationId: "reply_to_topic_api_v1_topics__topic_id__posts_post" };
    };
    "/api/v1/topics/{topic_id}/read-state": {
      put: { response: components["schemas"]["ApiResponse_TopicReadStateResponse_"]; operationId: "mark_topic_read_state_api_v1_topics__topic_id__read_state_put" };
    };
    "/api/v1/topics/{topic_id}/solution": {
      put: { response: components["schemas"]["ApiResponse_TopicResponse_"]; operationId: "set_topic_solution_api_v1_topics__topic_id__solution_put" };
    };
    "/api/v1/topics/{topic_id}/split": {
      post: { response: components["schemas"]["ApiResponse_TopicLifecycleResponse_"]; operationId: "split_topic_api_v1_topics__topic_id__split_post" };
    };
    "/api/v1/topics/{topic_id}/vote": {
      put: { response: components["schemas"]["ApiResponse_VoteStateResponse_"]; operationId: "vote_topic_api_v1_topics__topic_id__vote_put" };
    };
    "/api/v1/topics/immersive-feed": {
      get: { response: components["schemas"]["ApiResponse_list_ImmersiveTopicFeedItemResponse__"]; operationId: "list_immersive_topic_feed_api_v1_topics_immersive_feed_get" };
    };
    "/api/v1/uploads": {
      post: { response: components["schemas"]["ApiResponse_UploadResponse_"]; operationId: "upload_file_api_v1_uploads_post" };
    };
    "/api/v1/uploads/{upload_id}/content": {
      get: { response: unknown; operationId: "get_upload_content_api_v1_uploads__upload_id__content_get" };
    };
    "/api/v1/uploads/{upload_id}/thumbnail": {
      get: { response: unknown; operationId: "get_upload_thumbnail_api_v1_uploads__upload_id__thumbnail_get" };
    };
    "/api/v1/uploads/avatar": {
      post: { response: components["schemas"]["ApiResponse_UserPublic_"]; operationId: "upload_avatar_api_v1_uploads_avatar_post" };
    };
    "/api/v1/users/{username}": {
      get: { response: components["schemas"]["ApiResponse_UserProfileResponse_"]; operationId: "get_user_profile_api_v1_users__username__get" };
    };
    "/api/v1/users/{username}/activity": {
      get: { response: components["schemas"]["ApiResponse_list_UserActivityItemResponse__"]; operationId: "list_user_activity_api_v1_users__username__activity_get" };
    };
    "/api/v1/users/{username}/block": {
      delete: { response: components["schemas"]["ApiResponse_UserRelationshipStateResponse_"]; operationId: "unblock_user_api_v1_users__username__block_delete" };
      put: { response: components["schemas"]["ApiResponse_UserRelationshipStateResponse_"]; operationId: "block_user_api_v1_users__username__block_put" };
    };
    "/api/v1/users/{username}/follow": {
      delete: { response: components["schemas"]["ApiResponse_UserRelationshipStateResponse_"]; operationId: "unfollow_user_api_v1_users__username__follow_delete" };
      put: { response: components["schemas"]["ApiResponse_UserRelationshipStateResponse_"]; operationId: "follow_user_api_v1_users__username__follow_put" };
    };
    "/api/v1/users/{username}/ignore": {
      delete: { response: components["schemas"]["ApiResponse_UserRelationshipStateResponse_"]; operationId: "unignore_user_api_v1_users__username__ignore_delete" };
      put: { response: components["schemas"]["ApiResponse_UserRelationshipStateResponse_"]; operationId: "ignore_user_api_v1_users__username__ignore_put" };
    };
    "/api/v1/users/{username}/relationship": {
      get: { response: components["schemas"]["ApiResponse_UserRelationshipStateResponse_"]; operationId: "get_user_relationship_api_v1_users__username__relationship_get" };
    };
    "/api/v1/users/{username}/relationships/{kind}": {
      get: { response: components["schemas"]["ApiResponse_list_UserRelationshipUserResponse__"]; operationId: "list_user_relationships_api_v1_users__username__relationships__kind__get" };
    };
    "/api/v1/users/{username}/topics": {
      get: { response: components["schemas"]["ApiResponse_list_TopicResponse__"]; operationId: "list_user_topics_api_v1_users__username__topics_get" };
    };
    "/api/v1/users/directory": {
      get: { response: components["schemas"]["ApiResponse_list_UserDirectoryResponse__"]; operationId: "list_user_directory_api_v1_users_directory_get" };
    };
    "/api/v1/users/me": {
      delete: { response: components["schemas"]["ApiResponse_PrivacyActionResponse_"]; operationId: "delete_current_user_api_v1_users_me_delete" };
    };
    "/api/v1/users/me/export": {
      get: { response: unknown; operationId: "export_current_user_api_v1_users_me_export_get" };
    };
    "/api/v1/users/me/profile": {
      patch: { response: components["schemas"]["ApiResponse_UserProfileResponse_"]; operationId: "update_my_profile_api_v1_users_me_profile_patch" };
    };
    "/api/v1/users/messages": {
      get: { response: components["schemas"]["ApiResponse_list_PrivateMessageTopicResponse__"]; operationId: "list_private_messages_api_v1_users_messages_get" };
      post: { response: components["schemas"]["ApiResponse_PrivateMessageTopicResponse_"]; operationId: "create_private_message_api_v1_users_messages_post" };
    };
    "/api/v1/users/privacy/retention": {
      get: { response: components["schemas"]["ApiResponse_RetentionPolicyResponse_"]; operationId: "privacy_retention_policy_api_v1_users_privacy_retention_get" };
    };
    "/healthz": {
      get: { response: {
      [key: string]: string;
    }; operationId: "root_healthz_healthz_get" };
    };
    "/metrics": {
      get: { response: unknown; operationId: "metrics_metrics_get" };
    };
    "/p/{topic_id}": {
      get: { response: unknown; operationId: "compact_topic_redirect_p__topic_id__get" };
    };
    "/robots.txt": {
      get: { response: unknown; operationId: "robots_txt_robots_txt_get" };
    };
    "/sitemap.xml": {
      get: { response: unknown; operationId: "sitemap_xml_sitemap_xml_get" };
    };
    "/t/{legacy_slug}/{topic_id}": {
      get: { response: unknown; operationId: "legacy_topic_redirect_t__legacy_slug___topic_id__get" };
    };
}

export type ApiSchema<Name extends keyof components["schemas"]> = components["schemas"][Name];
export type ApiPath<Name extends keyof paths> = paths[Name];

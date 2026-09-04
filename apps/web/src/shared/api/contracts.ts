import type { UserPublic as AuthUserPublic, LoginResponse } from "@/features/auth/model";
import type { AdminUserResponse, AdminUserUpdateRequest } from "@/features/admin/model";
import type { BoardResponse } from "@/features/boards/model";
import type {
  DailyReportInput,
  DailyReportProfile,
  DailyReportRecord,
  DailyReportSession,
} from "@/features/dailyReports/model";
import type { PostResponse } from "@/features/posts/model";
import type { PdfTranslationCapabilities } from "@/features/pdfTranslations/model";
import type { MigrationUserRecord } from "@/features/migrations/model";
import type { UserRelationshipUser } from "@/features/social/model";
import type { CreateTopicRequest, PollResponse, TopicResponse } from "@/features/topics/model";
import type { UserDirectoryEntry, UserProfile } from "@/features/users/model";
import type { components } from "@/shared/api/generated";

type IsApiCompatible<Manual, Generated> = [Manual] extends [Generated] ? true : false;
type AssertApiCompatible<Check extends true> = Check;

export type ApiContractChecks = {
  adminUserResponse: AssertApiCompatible<
    IsApiCompatible<AdminUserResponse, components["schemas"]["AdminUserResponse"]>
  >;
  adminUserUpdateRequest: AssertApiCompatible<
    IsApiCompatible<AdminUserUpdateRequest, components["schemas"]["AdminUserUpdateRequest"]>
  >;
  boardResponse: AssertApiCompatible<
    IsApiCompatible<BoardResponse, components["schemas"]["BoardResponse"]>
  >;
  topicResponse: AssertApiCompatible<
    IsApiCompatible<TopicResponse, components["schemas"]["TopicResponse"]>
  >;
  postResponse: AssertApiCompatible<
    IsApiCompatible<PostResponse, components["schemas"]["PostResponse"]>
  >;
  pollResponse: AssertApiCompatible<
    IsApiCompatible<PollResponse, components["schemas"]["PollResponse"]>
  >;
  createTopicRequest: AssertApiCompatible<
    IsApiCompatible<CreateTopicRequest, components["schemas"]["TopicCreateRequest"]>
  >;
  userPublic: AssertApiCompatible<
    IsApiCompatible<AuthUserPublic, components["schemas"]["UserPublic"]>
  >;
  userProfile: AssertApiCompatible<
    IsApiCompatible<UserProfile, components["schemas"]["UserProfileResponse"]>
  >;
  userDirectory: AssertApiCompatible<
    IsApiCompatible<UserDirectoryEntry, components["schemas"]["UserDirectoryResponse"]>
  >;
  userRelationshipUser: AssertApiCompatible<
    IsApiCompatible<UserRelationshipUser, components["schemas"]["UserRelationshipUserResponse"]>
  >;
  migrationUserRecord: AssertApiCompatible<
    IsApiCompatible<MigrationUserRecord, components["schemas"]["MigrationUserRecord"]>
  >;
  loginResponse: AssertApiCompatible<
    IsApiCompatible<LoginResponse, components["schemas"]["LoginResponse"]>
  >;
  dailyReportInput: AssertApiCompatible<
    IsApiCompatible<DailyReportInput, components["schemas"]["DailyReportSessionStartRequest"]>
  >;
  dailyReportProfile: AssertApiCompatible<
    IsApiCompatible<DailyReportProfile, components["schemas"]["DailyReportProfileResponse"]>
  >;
  dailyReportSession: AssertApiCompatible<
    IsApiCompatible<DailyReportSession, components["schemas"]["DailyReportSessionResponse"]>
  >;
  dailyReportRecord: AssertApiCompatible<
    IsApiCompatible<DailyReportRecord, components["schemas"]["DailyReportResponse"]>
  >;
  pdfTranslationCapabilities: AssertApiCompatible<
    IsApiCompatible<
      PdfTranslationCapabilities,
      components["schemas"]["PdfTranslationCapabilities"]
    >
  >;
};

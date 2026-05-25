import type { UserPublic as AuthUserPublic, LoginResponse } from "@/features/auth/model";
import type { BoardResponse } from "@/features/boards/model";
import type { PostResponse } from "@/features/posts/model";
import type {
  CreateTopicRequest,
  PollResponse,
  TopicLifecycleResponse,
  TopicResponse,
} from "@/features/topics/model";
import type { UserDirectoryEntry, UserProfile } from "@/features/users/model";
import type { components } from "@/shared/api/generated";

type IsApiCompatible<Manual, Generated> = [Manual] extends [Generated] ? true : false;
type AssertApiCompatible<Check extends true> = Check;

export type ApiContractChecks = {
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
  topicLifecycleResponse: AssertApiCompatible<
    IsApiCompatible<TopicLifecycleResponse, components["schemas"]["TopicLifecycleResponse"]>
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
  loginResponse: AssertApiCompatible<
    IsApiCompatible<LoginResponse, components["schemas"]["LoginResponse"]>
  >;
};

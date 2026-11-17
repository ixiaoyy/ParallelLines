import { commonText } from "./common";
import { catalogText } from "./catalog";
import { adminText } from "./admin";
import { accountText } from "./account";
import { forumText } from "./forum";
import { spaceText } from "./space";
import { seoText } from "./seo";
import { toolsText } from "./tools";
import { analyticsText } from "./analytics";

// 按界面领域维护词条；业务内容继续由原 API 和作者提供，不进入此表。
export const EN_UI_TEXT: Record<string, string> = { ...commonText, ...catalogText, ...adminText, ...accountText, ...forumText, ...spaceText, ...seoText, ...toolsText, ...analyticsText };

import { describe, expect, it } from "vitest";

import { formatTrafficCount, formatTrafficPercent, formatTrafficTimestamp, trafficChange } from "./trafficModel";

describe("跨站流量展示口径", () => {
  it("区分缺失数据与已确认零流量", () => {
    expect(formatTrafficCount(null)).toBe("—");
    expect(formatTrafficCount(undefined)).toBe("—");
    expect(formatTrafficCount(0)).toBe("0");
    expect(formatTrafficCount(1234)).toBe("1,234");
  });

  it("前期为零时不输出无穷大增长，缺失对比不伪装持平", () => {
    expect(trafficChange(null, 0)).toBe("暂无可比数据");
    expect(trafficChange(0, null)).toBe("暂无可比数据");
    expect(trafficChange(0, 0)).toBe("与前期持平");
    expect(trafficChange(5, 0)).toBe("前期为 0，本期有新增");
    expect(trafficChange(15, 10)).toBe("较前期 +50%");
    expect(trafficChange(5, 10)).toBe("较前期 -50%");
  });

  it("回访率缺失不冒充零回访，沿用后端百分比口径", () => {
    expect(formatTrafficPercent(null)).toBe("—");
    expect(formatTrafficPercent(0)).toBe("0%");
    expect(formatTrafficPercent(33.3333)).toBe("33.3%");
  });

  it("按上海时区显示真实时间，缺失时间不生成记录", () => {
    expect(formatTrafficTimestamp("2026-11-17T00:00:00Z")).toBe("11/17 08:00");
    expect(formatTrafficTimestamp(null)).toBe("尚无记录");
    expect(formatTrafficTimestamp("invalid")).toBe("尚无记录");
  });
});

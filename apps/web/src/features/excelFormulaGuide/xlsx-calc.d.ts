declare module "xlsx-calc" {
  interface XlsxCalculator {
    (workbook: unknown, options?: { continue_after_error?: boolean; log_error?: boolean }): void;
    import_functions(functions: Record<string, unknown>, options?: { override?: boolean }): void;
    import_raw_functions(functions: Record<string, unknown>): void;
    set_fx(name: string, fn: (...args: unknown[]) => unknown): void;
  }
  const calculate: XlsxCalculator;
  export default calculate;
}

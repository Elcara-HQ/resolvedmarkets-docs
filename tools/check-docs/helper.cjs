const fs = require("fs");
const ts = require("typescript");

const cmd = process.argv[2];
const input = fs.readFileSync(0, "utf8");

if (cmd === "configs") {
  const out = ts.transpileModule(input, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  });
  const mod = { exports: {} };
  const tail = "\nmodule.exports.__cities = DAILY_TEMP_CITIES;";
  new Function("module", "exports", out.outputText + tail)(mod, mod.exports);
  const configs = mod.exports.MARKET_CATEGORIES.map((c) => ({
    id: c.id,
    category: c.category,
    group: c.group ?? null,
    displayName: c.displayName,
    captureIntervalMs: c.captureIntervalMs,
    refreshIntervalMs: c.refreshIntervalMs,
    enabled: c.enabled,
  }));
  const cities = Object.values(mod.exports.__cities);
  process.stdout.write(
    JSON.stringify({
      configs,
      cityCount: cities.length,
      lowCityCount: cities.filter((c) => c.low).length,
    }),
  );
} else if (cmd === "syntax") {
  const items = JSON.parse(input);
  const diagsFor = (code, fileName) => {
    const out = ts.transpileModule(code, {
      fileName,
      reportDiagnostics: true,
      compilerOptions: {
        allowJs: true,
        jsx: ts.JsxEmit.Preserve,
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
      },
    });
    return (out.diagnostics || []).map((d) => ts.flattenDiagnosticMessageText(d.messageText, " "));
  };
  const names = { javascript: ["js", "jsx"], js: ["js", "jsx"], jsx: ["jsx"], typescript: ["ts", "tsx"], ts: ["ts", "tsx"], tsx: ["tsx"] };
  const results = items.map((item) => {
    let diags = [];
    for (const ext of names[item.lang]) {
      diags = diagsFor(item.code, `block.${ext}`);
      if (diags.length === 0) break;
    }
    return { name: item.name, diags };
  });
  process.stdout.write(JSON.stringify(results));
} else {
  process.stderr.write(`unknown command: ${cmd}\n`);
  process.exit(2);
}

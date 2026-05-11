const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");

// Icons
const { FaDatabase, FaRobot, FaSearch, FaShieldAlt, FaChartBar, FaUserCheck,
        FaBrain, FaBalanceScale, FaFileAlt, FaCheckCircle, FaExclamationTriangle,
        FaCogs, FaLayerGroup, FaCode, FaHistory, FaArrowRight } = require("react-icons/fa");
const { MdGavel, MdPolicy, MdAccountBalance, MdSecurity } = require("react-icons/md");

async function iconPng(IconComponent, color = "#FFFFFF", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const C = {
  darkBg:   "0D1B2A",
  midBg:    "112233",
  cardBg:   "16304A",
  accent:   "C8A951",   // gold
  accentDim:"8B6914",
  blue:     "1B6CA8",
  lightBlue:"3A9BD5",
  white:    "FFFFFF",
  offWhite: "E8EEF4",
  muted:    "8AA0B8",
  red:      "C0392B",
  green:    "27AE60",
  teal:     "1ABC9C",
};

function makeShadow() {
  return { type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.25 };
}

let pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "面向政策资格认定的多智能体辩论式Text-to-SQL智能评审系统";

// ─── Slide 0: Cover ─────────────────────────────────────────────────────────
{
  let s = pres.addSlide();
  s.background = { color: C.darkBg };

  // Top accent bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent }, line: { color: C.accent } });

  // Left vertical gold bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 1.0, w: 0.07, h: 3.6, fill: { color: C.accent }, line: { color: C.accent } });

  // Main title
  s.addText("面向政策资格认定的", {
    x: 0.8, y: 1.0, w: 8.5, h: 0.75,
    fontSize: 30, bold: true, color: C.offWhite, fontFace: "Microsoft YaHei",
    margin: 0
  });
  s.addText("多智能体辩论式 Text-to-SQL", {
    x: 0.8, y: 1.75, w: 8.5, h: 0.85,
    fontSize: 34, bold: true, color: C.accent, fontFace: "Microsoft YaHei",
    margin: 0
  });
  s.addText("智能评审系统", {
    x: 0.8, y: 2.6, w: 8.5, h: 0.75,
    fontSize: 30, bold: true, color: C.offWhite, fontFace: "Microsoft YaHei",
    margin: 0
  });

  // Subtitle line
  s.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 3.5, w: 4.5, h: 0.04, fill: { color: C.muted }, line: { color: C.muted } });

  s.addText("Policy Eligibility Adjudication via Multi-Agent Debate & Text-to-SQL", {
    x: 0.8, y: 3.65, w: 8.5, h: 0.4,
    fontSize: 12, italic: true, color: C.muted, fontFace: "Calibri", margin: 0
  });

  // Tag pills
  const tags = ["政务AI", "Text-to-SQL", "多智能体", "证据推理", "可解释AI"];
  tags.forEach((t, i) => {
    const x = 0.8 + i * 1.82;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 4.2, w: 1.65, h: 0.38, fill: { color: C.cardBg }, line: { color: C.accent, width: 1 }, rectRadius: 0.05
    });
    s.addText(t, { x, y: 4.2, w: 1.65, h: 0.38, fontSize: 11, color: C.accent, align: "center", valign: "middle", fontFace: "Microsoft YaHei" });
  });

  // Bottom: section nav
  const sections = ["背景介绍", "系统设计", "方案实现", "系统测试", "创新与应用"];
  sections.forEach((sec, i) => {
    const x = 0.5 + i * 1.82;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 4.9, w: 1.65, h: 0.5, fill: { color: C.blue }, line: { color: C.lightBlue, width: 1 }
    });
    s.addText(`0${i+1}  ${sec}`, { x, y: 4.9, w: 1.65, h: 0.5, fontSize: 11, color: C.white, align: "center", valign: "middle", fontFace: "Microsoft YaHei" });
  });

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.57, w: 10, h: 0.055, fill: { color: C.accent }, line: { color: C.accent } });
}

// ─── CHAPTER TITLE helper ────────────────────────────────────────────────────
function chapterSlide(pres, num, title, subtitle) {
  let s = pres.addSlide();
  s.background = { color: C.darkBg };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent }, line: { color: C.accent } });
  // Big number watermark
  s.addText(`0${num}`, {
    x: 6.5, y: 0.5, w: 3.5, h: 4.5, fontSize: 200, color: C.cardBg, bold: true,
    fontFace: "Arial Black", align: "right", valign: "middle", margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 1.6, w: 0.1, h: 2.0, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText(`0${num}`, { x: 0.8, y: 1.6, w: 1.2, h: 0.55, fontSize: 28, color: C.accent, bold: true, fontFace: "Arial Black", margin: 0 });
  s.addText(title, { x: 0.8, y: 2.2, w: 7, h: 0.8, fontSize: 36, bold: true, color: C.white, fontFace: "Microsoft YaHei", margin: 0 });
  s.addText(subtitle, { x: 0.8, y: 3.1, w: 7, h: 0.5, fontSize: 14, color: C.muted, fontFace: "Microsoft YaHei", italic: true, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.57, w: 10, h: 0.055, fill: { color: C.accent }, line: { color: C.accent } });
  return s;
}

// Slide header helper
function slideHeader(s, pres, num, chTitle, slideTitle) {
  s.background = { color: "F4F7FA" };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: C.darkBg }, line: { color: C.darkBg } });
  s.addText(`0${num}  ${chTitle}`, { x: 0.3, y: 0, w: 3.5, h: 0.55, fontSize: 11, color: C.muted, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 3.8, y: 0, w: 0.04, h: 0.55, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText(slideTitle, { x: 4.0, y: 0, w: 5.5, h: 0.55, fontSize: 14, bold: true, color: C.accent, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.57, w: 10, h: 0.055, fill: { color: C.darkBg }, line: { color: C.darkBg } });
}

// Card helper
function addCard(s, pres, x, y, w, h, opts = {}) {
  s.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: opts.fill || C.white },
    line: { color: opts.border || "D4DCE8", width: opts.lineW || 1 },
    shadow: opts.shadow !== false ? makeShadow() : undefined
  });
  if (opts.accentLeft) {
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.07, h, fill: { color: opts.accentLeft }, line: { color: opts.accentLeft } });
  }
}

// ═══════════════════════════════════════════════════════════════════
// 01 背景介绍
// ═══════════════════════════════════════════════════════════════════
chapterSlide(pres, 1, "背景介绍", "政务审核的现实痛点与智能化机遇");

// Slide 01-A: 痛点分析
{
  let s = pres.addSlide();
  slideHeader(s, pres, 1, "背景介绍", "传统政务资格审核的五大痛点");

  const pain = [
    { icon: "⚖️", title: "人工经验依赖", body: "政策条款解读依赖审核人员个人经验，同一条款在不同办事人员间存在解释差异，难以保证结果一致性。" },
    { icon: "🗄️", title: "数据分散核查难", body: "申请人信息分布于就业、参保、补贴等多张业务数据库，人工逐表核验成本极高，容易发生遗漏。" },
    { icon: "🤖", title: "大模型幻觉风险", body: "直接使用大语言模型进行资格判断，缺乏数据库事实约束，模型可能凭训练印象编造不存在的证据。" },
    { icon: "📋", title: "单一视角决策", body: "单一AI智能体给出结论简洁但视角单一，无法充分暴露政策争议点，容易遗漏边界情形。" },
    { icon: "🔍", title: "缺乏可追溯证据链", body: "自动化系统给出结论却无法说明依据，无法满足政务审核'留痕可追溯'的合规要求和人工复核需求。" },
  ];

  pain.forEach((p, i) => {
    const col = i < 3 ? 0 : 1;
    const row = i < 3 ? i : i - 3;
    const x = 0.3 + col * 4.85;
    const y = 0.75 + row * 1.45;
    addCard(s, pres, x, y, 4.6, 1.3, { accentLeft: C.red });
    s.addText(p.icon + "  " + p.title, {
      x: x + 0.2, y: y + 0.12, w: 4.2, h: 0.4,
      fontSize: 13, bold: true, color: C.darkBg, fontFace: "Microsoft YaHei", margin: 0
    });
    s.addText(p.body, {
      x: x + 0.2, y: y + 0.52, w: 4.2, h: 0.65,
      fontSize: 10.5, color: "445566", fontFace: "Microsoft YaHei", margin: 0
    });
  });
  // 5th card lower right
  const p = pain[4];
  addCard(s, pres, 5.15, 0.75, 4.6, 1.3, { accentLeft: C.red });
  // already rendered above in loop col=1 row=1, skip duplicate
}

// Slide 01-B: 市场背景 + 本项目定位
{
  let s = pres.addSlide();
  slideHeader(s, pres, 1, "背景介绍", "政务智能化趋势与本项目定位");

  // Left: background context
  addCard(s, pres, 0.3, 0.7, 4.5, 4.6, { fill: C.darkBg, shadow: false });
  s.addText("政策背景", { x: 0.5, y: 0.85, w: 4.1, h: 0.45, fontSize: 16, bold: true, color: C.accent, fontFace: "Microsoft YaHei", margin: 0 });
  const bgPoints = [
    "「十四五」规划明确推进数字政府建设，政务服务向主动化、智能化转型",
    "社保补贴、灵活就业认定等涉及数亿人次，资格审核量大面广",
    "传统人工审核模式效率瓶颈凸显，基层人员负担日益加重",
    "国家要求政务流程\"留痕可追溯\"，自动化决策需具备可解释性",
    "AI大模型技术成熟，为政务辅助审核提供新的技术可能",
  ];
  bgPoints.forEach((pt, i) => {
    s.addShape(pres.shapes.OVAL, { x: 0.5, y: 1.5 + i * 0.72, w: 0.22, h: 0.22, fill: { color: C.accent }, line: { color: C.accent } });
    s.addText(pt, { x: 0.82, y: 1.46 + i * 0.72, w: 3.8, h: 0.38, fontSize: 11, color: C.offWhite, fontFace: "Microsoft YaHei", margin: 0 });
  });

  // Right: our solution positioning
  addCard(s, pres, 5.0, 0.7, 4.7, 4.6, { fill: C.white });
  s.addText("本项目核心定位", { x: 5.2, y: 0.85, w: 4.3, h: 0.45, fontSize: 16, bold: true, color: C.blue, fontFace: "Microsoft YaHei", margin: 0 });

  const pos = [
    { color: C.teal, label: "不替代人工", desc: "系统作为智能辅助工具，保留人工复核入口" },
    { color: C.blue, label: "事实约束推理", desc: "以SQL数据库查询结果作为判断边界，避免幻觉" },
    { color: C.accent, label: "多角色博弈", desc: "六类智能体角色模拟真实审核委员会决策过程" },
    { color: C.green, label: "全程可追溯", desc: "每个结论对应明确的证据卡片和条款引用" },
    { color: C.red, label: "工程闭环", desc: "从输入到报告生成，覆盖完整业务链路" },
  ];
  pos.forEach((p, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.48 + i * 0.72, w: 0.18, h: 0.35, fill: { color: p.color }, line: { color: p.color } });
    s.addText(p.label, { x: 5.38, y: 1.45 + i * 0.72, w: 1.3, h: 0.38, fontSize: 12, bold: true, color: C.darkBg, fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(p.desc, { x: 6.75, y: 1.45 + i * 0.72, w: 2.8, h: 0.38, fontSize: 10.5, color: "445566", fontFace: "Microsoft YaHei", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════
// 02 系统设计
// ═══════════════════════════════════════════════════════════════════
chapterSlide(pres, 2, "系统设计", "架构、模块分层与数据流设计");

// Slide 02-A: 整体架构图
{
  let s = pres.addSlide();
  slideHeader(s, pres, 2, "系统设计", "系统总体架构");

  // Layer boxes
  const layers = [
    { label: "前端展示层", sub: "Vue 3 + Vite + Element Plus", color: C.accent, x: 0.3, y: 0.7, w: 9.4, h: 0.72 },
    { label: "API 接口层", sub: "FastAPI · 流式SSE · 参数校验", color: C.lightBlue, x: 0.3, y: 1.55, w: 9.4, h: 0.72 },
    { label: "意图理解 & 政策路由", sub: "自然语言→政策ID映射", color: C.blue, x: 0.3, y: 2.4, w: 2.9, h: 0.72 },
    { label: "政策认知 & 规则结构化", sub: "条款→机器可读规则", color: C.blue, x: 3.35, y: 2.4, w: 3.1, h: 0.72 },
    { label: "Text-to-SQL 取证", sub: "SQL生成·修复·证据装配", color: C.blue, x: 6.6, y: 2.4, w: 3.1, h: 0.72 },
    { label: "证据模型层", sub: "EvidenceBundle · 诊断标签", color: "28707A", x: 0.3, y: 3.25, w: 4.5, h: 0.72 },
    { label: "多智能体辩论层", sub: "6角色 · 辩论编排 · 仲裁裁决", color: "28707A", x: 4.95, y: 3.25, w: 4.75, h: 0.72 },
    { label: "持久化层", sub: "MySQL · 会话 · 历史复核", color: "3A4A5A", x: 0.3, y: 4.1, w: 9.4, h: 0.72 },
  ];

  layers.forEach(l => {
    s.addShape(pres.shapes.RECTANGLE, { x: l.x, y: l.y, w: l.w, h: l.h, fill: { color: l.color }, line: { color: l.color } });
    s.addText(l.label, { x: l.x + 0.15, y: l.y + 0.04, w: l.w - 0.3, h: 0.38, fontSize: 13, bold: true, color: C.white, fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(l.sub, { x: l.x + 0.15, y: l.y + 0.4, w: l.w - 0.3, h: 0.28, fontSize: 9.5, color: "D0E8F8", fontFace: "Calibri", margin: 0 });
  });

  // Arrows between layers
  [[1.18, 1.42], [1.18, 2.27], [1.18, 3.12], [1.18, 3.97]].forEach(([y1]) => {
    s.addShape(pres.shapes.LINE, { x: 5.0, y: y1, w: 0, h: 0.13, line: { color: C.muted, width: 1.5 } });
  });
}

// Slide 02-B: 6智能体角色设计
{
  let s = pres.addSlide();
  slideHeader(s, pres, 2, "系统设计", "多智能体角色分工设计");

  s.addText("系统设计了六种角色智能体，模拟真实政务审核委员会中不同岗位、不同思维方式的审核者。", {
    x: 0.3, y: 0.65, w: 9.4, h: 0.4, fontSize: 12, color: "445566", fontFace: "Microsoft YaHei", margin: 0
  });

  const agents = [
    { name: "严格合规智能体", en: "Compliance Agent", color: C.red, icon: "⚖️", desc: "严格按政策条款逐条核查，不接受任何模糊解释，把控合规底线" },
    { name: "宽松业务智能体", en: "Business Agent", color: C.blue, icon: "💼", desc: "关注政策执行弹性，考虑实际业务情境，避免一刀切拒绝" },
    { name: "审计复核智能体", en: "Audit Agent", color: C.accentDim, icon: "🔍", desc: "专注识别风险点、数据异常和证据缺口，提出预警和质疑" },
    { name: "经验案例智能体", en: "Case Agent", color: C.teal, icon: "📚", desc: "参考历史类似案例进行辅助判断，提供经验参照和先例支撑" },
    { name: "探索补充智能体", en: "Explore Agent", color: "7D3C98", icon: "🧭", desc: "主动发现可能遗漏的审查视角，提出补证方向和延伸问题" },
    { name: "仲裁裁决智能体", en: "Arbiter Agent", color: C.darkBg, icon: "🔨", desc: "汇总多轮辩论，权衡共识与冲突，最终形成有据可查的裁决" },
  ];

  agents.forEach((a, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.3 + col * 3.2;
    const y = 1.2 + row * 2.1;
    addCard(s, pres, x, y, 3.0, 1.85, { fill: C.white, shadow: true });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 3.0, h: 0.45, fill: { color: a.color }, line: { color: a.color } });
    s.addText(a.icon + "  " + a.name, { x: x + 0.1, y: y + 0.04, w: 2.8, h: 0.37, fontSize: 12, bold: true, color: C.white, fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(a.en, { x: x + 0.12, y: y + 0.5, w: 2.8, h: 0.3, fontSize: 9.5, color: C.muted, italic: true, fontFace: "Calibri", margin: 0 });
    s.addText(a.desc, { x: x + 0.12, y: y + 0.82, w: 2.78, h: 0.9, fontSize: 10.5, color: "334455", fontFace: "Microsoft YaHei", margin: 0 });
  });
}

// Slide 02-C: 主流程设计
{
  let s = pres.addSlide();
  slideHeader(s, pres, 2, "系统设计", "审查主流程 · 先取证后推理");

  const steps = [
    { n: "01", label: "用户输入", sub: "自然语言诉求\n或身份证号", color: C.blue },
    { n: "02", label: "意图识别", sub: "政策路由\n确认适用政策", color: C.blue },
    { n: "03", label: "规则加载", sub: "结构化政策\n条款拆解", color: C.teal },
    { n: "04", label: "SQL取证", sub: "动态生成SQL\n自动修复执行", color: C.teal },
    { n: "05", label: "证据装配", sub: "EvidenceBundle\n诊断标签", color: "28707A" },
    { n: "06", label: "多轮辩论", sub: "六角色审查\n共识检测", color: "28707A" },
    { n: "07", label: "仲裁裁决", sub: "条款级结论\n可追溯报告", color: C.accent },
    { n: "08", label: "人工复核", sub: "补证闭环\n历史存档", color: C.accentDim },
  ];

  // Two rows of 4
  steps.forEach((st, i) => {
    const row = Math.floor(i / 4);
    const col = i % 4;
    const x = 0.3 + col * 2.35;
    const y = 0.75 + row * 2.3;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 2.1, h: 1.95,
      fill: { color: st.color }, line: { color: st.color },
      shadow: makeShadow()
    });
    s.addText(st.n, { x, y: y + 0.1, w: 2.1, h: 0.5, fontSize: 28, bold: true, color: "FFFFFF30", align: "center", fontFace: "Arial Black", margin: 0 });
    s.addText(st.label, { x, y: y + 0.65, w: 2.1, h: 0.45, fontSize: 14, bold: true, color: C.white, align: "center", fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(st.sub, { x, y: y + 1.12, w: 2.1, h: 0.7, fontSize: 10, color: "D0E8F8", align: "center", fontFace: "Microsoft YaHei", margin: 0 });

    // Arrow (not after last in each row)
    if (col < 3) {
      s.addShape(pres.shapes.LINE, { x: x + 2.1, y: y + 0.95, w: 0.25, h: 0, line: { color: C.muted, width: 2 } });
    }
  });

  s.addText("「先取证、后推理」确保大模型在结构化事实约束下进行审查，从根本上抑制幻觉风险", {
    x: 0.3, y: 5.1, w: 9.4, h: 0.35, fontSize: 11, italic: true, color: C.blue, align: "center", fontFace: "Microsoft YaHei", margin: 0
  });
}

// ═══════════════════════════════════════════════════════════════════
// 03 方案实现
// ═══════════════════════════════════════════════════════════════════
chapterSlide(pres, 3, "方案实现", "核心模块技术实现与关键设计");

// Slide 03-A: Text-to-SQL链路
{
  let s = pres.addSlide();
  slideHeader(s, pres, 3, "方案实现", "Text-to-SQL 取证链路");

  // Left: pipeline
  addCard(s, pres, 0.3, 0.7, 4.3, 4.65, { fill: C.darkBg, shadow: false });
  s.addText("取证执行流水线", { x: 0.5, y: 0.82, w: 3.9, h: 0.42, fontSize: 14, bold: true, color: C.accent, fontFace: "Microsoft YaHei", margin: 0 });
  const pipe = [
    "① 加载政策条款 & Schema认知",
    "② 字典映射（人员身份/参保状态等）",
    "③ 动态SQL生成 / 模板匹配",
    "④ SQL执行 → 结果采集",
    "⑤ 结果校验（匹配期望？）",
    "⑥ 不匹配 → 自动调试修复",
    "⑦ 组装 EvidenceBundle",
  ];
  pipe.forEach((p, i) => {
    const active = i === 5;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 1.38 + i * 0.48, w: 3.95, h: 0.4, fill: { color: active ? C.accent : C.cardBg }, line: { color: active ? C.accent : C.blue, width: 1 } });
    s.addText(p, { x: 0.55, y: 1.38 + i * 0.48, w: 3.75, h: 0.4, fontSize: 11, color: active ? C.darkBg : C.offWhite, fontFace: "Microsoft YaHei", valign: "middle", margin: 0, bold: active });
  });

  // Right: evidence card structure
  addCard(s, pres, 4.8, 0.7, 4.9, 4.65, { fill: C.white });
  s.addText("证据卡片结构（EvidenceItem）", { x: 5.0, y: 0.82, w: 4.5, h: 0.42, fontSize: 14, bold: true, color: C.blue, fontFace: "Microsoft YaHei", margin: 0 });
  const fields = [
    ["规则编号", "对应政策条款ID"],
    ["查询对象", "目标人员信息"],
    ["执行SQL", "完整SQL语句"],
    ["查询结果", "数据库原始返回"],
    ["结果摘要", "面向审查的摘要"],
    ["执行状态", "success / error"],
    ["诊断标签", "异常/缺失/冲突"],
    ["置信度", "0.0 ~ 1.0"],
    ["是否支持结论", "true / false"],
  ];
  fields.forEach((f, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 4.95, y: 1.38 + i * 0.39, w: 1.5, h: 0.33, fill: { color: C.darkBg }, line: { color: C.darkBg } });
    s.addText(f[0], { x: 4.95, y: 1.38 + i * 0.39, w: 1.5, h: 0.33, fontSize: 10, color: C.accent, align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(f[1], { x: 6.52, y: 1.38 + i * 0.39, w: 3.0, h: 0.33, fontSize: 10, color: "334455", valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  });
}

// Slide 03-B: 多智能体辩论流程
{
  let s = pres.addSlide();
  slideHeader(s, pres, 3, "方案实现", "多智能体辩论 & 仲裁裁决流程");

  // Debate rounds
  s.addText("辩论编排逻辑：角色分工 → 轮次辩论 → 共识检测 → 仲裁整合", {
    x: 0.3, y: 0.65, w: 9.4, h: 0.35, fontSize: 12, color: "445566", fontFace: "Microsoft YaHei", margin: 0
  });

  // Input
  addCard(s, pres, 0.3, 1.1, 2.0, 0.65, { fill: C.teal, shadow: false });
  s.addText("EvidenceBundle\n证据包输入", { x: 0.3, y: 1.1, w: 2.0, h: 0.65, fontSize: 10.5, color: C.white, align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });

  // Round 1
  addCard(s, pres, 2.6, 0.85, 5.0, 1.15, { fill: C.white });
  s.addShape(pres.shapes.RECTANGLE, { x: 2.6, y: 0.85, w: 5.0, h: 0.35, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("第一轮：各角色独立审查", { x: 2.65, y: 0.85, w: 4.9, h: 0.35, fontSize: 11, bold: true, color: C.white, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  ["严格合规", "宽松业务", "审计复核"].forEach((ag, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.75 + i * 1.6, y: 1.28, w: 1.45, h: 0.55, fill: { color: "EEF4FB" }, line: { color: C.blue, width: 1 }, rectRadius: 0.05 });
    s.addText(ag, { x: 2.75 + i * 1.6, y: 1.28, w: 1.45, h: 0.55, fontSize: 10, color: C.blue, align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  });

  // Round 2
  addCard(s, pres, 2.6, 2.2, 5.0, 1.15, { fill: C.white });
  s.addShape(pres.shapes.RECTANGLE, { x: 2.6, y: 2.2, w: 5.0, h: 0.35, fill: { color: "28707A" }, line: { color: "28707A" } });
  s.addText("第二轮：交叉质询与补充", { x: 2.65, y: 2.2, w: 4.9, h: 0.35, fontSize: 11, bold: true, color: C.white, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  ["经验案例", "探索补充"].forEach((ag, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.75 + i * 2.4, y: 2.62, w: 2.2, h: 0.55, fill: { color: "E8F8F5" }, line: { color: "28707A", width: 1 }, rectRadius: 0.05 });
    s.addText(ag + "\n加入异见与补充", { x: 2.75 + i * 2.4, y: 2.62, w: 2.2, h: 0.55, fontSize: 10, color: "28707A", align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  });

  // Consensus check
  addCard(s, pres, 2.6, 3.55, 5.0, 0.75, { fill: "FFF8E1" });
  s.addText("🔎  共识检测：结论一致？证据覆盖？冲突是否可调和？", {
    x: 2.7, y: 3.55, w: 4.8, h: 0.75, fontSize: 11, color: C.accentDim, align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0
  });

  // Arbiter
  addCard(s, pres, 2.6, 4.45, 5.0, 0.75, { fill: C.darkBg });
  s.addText("🔨  仲裁智能体：综合裁决  →  条款级结论  →  官方报告", {
    x: 2.7, y: 4.45, w: 4.8, h: 0.75, fontSize: 11, color: C.accent, align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0
  });

  // Output
  addCard(s, pres, 7.85, 1.1, 1.9, 0.65, { fill: "27AE6020", shadow: false, border: C.green });
  s.addText("AdjudicationReport\n裁决报告", { x: 7.85, y: 1.1, w: 1.9, h: 0.65, fontSize: 10, color: C.green, align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });

  // Arrows
  s.addShape(pres.shapes.LINE, { x: 2.3, y: 1.43, w: 0.3, h: 0, line: { color: C.muted, width: 1.5 } });
  s.addShape(pres.shapes.LINE, { x: 2.3, y: 2.78, w: 0.3, h: 0, line: { color: C.muted, width: 1.5 } });
}

// Slide 03-C: 前端设计
{
  let s = pres.addSlide();
  slideHeader(s, pres, 3, "方案实现", "前端可视化系统设计");

  s.addText("采用「政务司法」视觉语言设计，红金配色体现权威性，围绕「可信审查」构建完整交互闭环。", {
    x: 0.3, y: 0.65, w: 9.4, h: 0.38, fontSize: 11.5, color: "445566", fontFace: "Microsoft YaHei", margin: 0
  });

  const modules = [
    { title: "政策识别面板", desc: "展示意图识别结果，确认适用政策，列出所有政策条款和条件", icon: "📋", color: C.red },
    { title: "人员画像区", desc: "基础信息、参保状态、就业形式等关键字段一目了然", icon: "👤", color: C.blue },
    { title: "证据卡片列表", desc: "每条SQL查询结果结构化展示，含状态标签和诊断信息", icon: "🗂️", color: C.teal },
    { title: "智能体观点面板", desc: "六角色观点分栏展示，支持多轮辩论时间线滚动回放", icon: "🤖", color: "28707A" },
    { title: "仲裁报告区", desc: "条款级判断、证据引用、风险提示、官方报告一键导出", icon: "📑", color: C.accent },
    { title: "人工复核面板", desc: "补充材料入口、再审触发、历史会话查看，形成完整闭环", icon: "✅", color: C.green },
  ];

  modules.forEach((m, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.3 + col * 3.2;
    const y = 1.15 + row * 2.1;
    addCard(s, pres, x, y, 3.0, 1.9, { fill: C.white });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 3.0, h: 0.5, fill: { color: m.color }, line: { color: m.color } });
    s.addText(m.icon + "  " + m.title, { x: x + 0.1, y, w: 2.8, h: 0.5, fontSize: 12.5, bold: true, color: C.white, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(m.desc, { x: x + 0.12, y: y + 0.58, w: 2.78, h: 1.2, fontSize: 11, color: "334455", fontFace: "Microsoft YaHei", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════
// 04 系统测试
// ═══════════════════════════════════════════════════════════════════
chapterSlide(pres, 4, "系统测试", "SQL链路评测与多智能体消融实验");

// Slide 04-A: SQL链路测试
{
  let s = pres.addSlide();
  slideHeader(s, pres, 4, "系统测试", "Text-to-SQL 链路评测结果");

  s.addText("80个测试样本，覆盖简单查询、条件过滤、聚合统计、多表关联四类场景。", {
    x: 0.3, y: 0.65, w: 9.4, h: 0.38, fontSize: 11.5, color: "445566", fontFace: "Microsoft YaHei", margin: 0
  });

  // Key metrics
  const metrics = [
    { label: "SQL生成成功率", val: "100%", color: C.green },
    { label: "首次执行成功率", val: "100%", color: C.green },
    { label: "首次结果匹配率", val: "62.5%", color: C.accent },
    { label: "最终结果匹配率", val: "87.5%", color: C.teal },
    { label: "修复成功率", val: "66.7%", color: C.blue },
    { label: "结构性警告率↓", val: "7.5%", color: C.green },
  ];
  metrics.forEach((m, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.3 + col * 3.2;
    const y = 1.15 + row * 1.25;
    addCard(s, pres, x, y, 3.0, 1.1, { fill: C.white, accentLeft: m.color });
    s.addText(m.val, { x: x + 0.25, y: y + 0.08, w: 2.7, h: 0.6, fontSize: 34, bold: true, color: m.color, fontFace: "Arial Black", margin: 0 });
    s.addText(m.label, { x: x + 0.25, y: y + 0.7, w: 2.7, h: 0.35, fontSize: 11, color: "445566", fontFace: "Microsoft YaHei", margin: 0 });
  });

  // Bar chart: with vs without repair
  s.addChart(pres.charts.BAR, [
    { name: "无修复链路", labels: ["结果匹配率", "结构性警告率"], values: [65, 32.5] },
    { name: "启用修复后", labels: ["结果匹配率", "结构性警告率"], values: [87.5, 7.5] },
  ], {
    x: 0.3, y: 3.75, w: 9.4, h: 1.6,
    barDir: "col", barGrouping: "clustered",
    chartColors: ["C0392B", "1ABC9C"],
    chartArea: { fill: { color: "F8FAFB" } },
    catAxisLabelColor: "445566", valAxisLabelColor: "445566",
    valGridLine: { color: "E0E8F0", size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelColor: "1E293B",
    showLegend: true, legendPos: "r",
  });
}

// Slide 04-B: 消融实验
{
  let s = pres.addSlide();
  slideHeader(s, pres, 4, "系统测试", "多智能体消融实验结果");

  s.addText("对比四种实验配置，验证证据约束与多角色辩论对决策质量的独立贡献。", {
    x: 0.3, y: 0.65, w: 9.4, h: 0.35, fontSize: 11.5, color: "445566", fontFace: "Microsoft YaHei", margin: 0
  });

  // Table
  const tableData = [
    [
      { text: "实验组", options: { bold: true, color: C.white, fill: { color: C.darkBg }, align: "center" } },
      { text: "结论准确率", options: { bold: true, color: C.white, fill: { color: C.darkBg }, align: "center" } },
      { text: "综合质量分", options: { bold: true, color: C.white, fill: { color: C.darkBg }, align: "center" } },
      { text: "严格通过率", options: { bold: true, color: C.white, fill: { color: C.darkBg }, align: "center" } },
      { text: "理由完整率", options: { bold: true, color: C.white, fill: { color: C.darkBg }, align: "center" } },
      { text: "证据引用率", options: { bold: true, color: C.white, fill: { color: C.darkBg }, align: "center" } },
    ],
    ["Single Agent", "87.50%", "80.83%", "41.67%", "70.83%", "62.50%"],
    ["Pro-Con Debate", "87.50%", "85.63%", "54.17%", "83.33%", "68.75%"],
    [
      { text: "No Evidence Constraint", options: { color: C.red, bold: true } },
      { text: "12.50% ⚠️", options: { color: C.red, bold: true, align: "center" } },
      { text: "43.12%", options: { color: C.red, align: "center" } },
      { text: "0.00%", options: { color: C.red, align: "center" } },
      { text: "75.00%", options: { align: "center" } },
      { text: "0.00%", options: { color: C.red, align: "center" } },
    ],
    [
      { text: "Full Multi-Agent ★", options: { color: C.teal, bold: true } },
      { text: "87.50%", options: { color: C.teal, bold: true, align: "center" } },
      { text: "91.04% ↑", options: { color: C.teal, bold: true, align: "center" } },
      { text: "70.83% ↑", options: { color: C.teal, bold: true, align: "center" } },
      { text: "91.67% ↑", options: { color: C.teal, bold: true, align: "center" } },
      { text: "84.72% ↑", options: { color: C.teal, bold: true, align: "center" } },
    ],
  ];
  s.addTable(tableData, {
    x: 0.3, y: 1.1, w: 9.4, h: 2.1,
    border: { pt: 1, color: "D0DCE8" },
    fill: { color: "F8FAFB" },
    fontSize: 11, fontFace: "Microsoft YaHei",
    align: "center",
    colW: [2.4, 1.4, 1.4, 1.4, 1.4, 1.4],
  });

  // Conclusions
  const conclusions = [
    { icon: "✅", color: C.teal, text: "完整多智能体链路综合决策质量最优（91.04分），严格通过率达70.83%" },
    { icon: "⚠️", color: C.red, text: "去除证据约束后准确率骤降至12.5%——证据约束是系统可靠性的绝对基础" },
    { icon: "📈", color: C.blue, text: "正反辩论相比单智能体，综合质量提升4.8分，严格通过率提升12.5个百分点" },
    { icon: "💡", color: C.accent, text: "高共识不等于高质量：No Evidence组共识100%但质量仅43分" },
  ];
  conclusions.forEach((c, i) => {
    addCard(s, pres, 0.3, 3.35 + i * 0.53, 9.4, 0.46, { fill: C.white, accentLeft: c.color });
    s.addText(c.icon + "  " + c.text, {
      x: 0.5, y: 3.35 + i * 0.53, w: 9.0, h: 0.46,
      fontSize: 11, color: "334455", fontFace: "Microsoft YaHei", valign: "middle", margin: 0
    });
  });
}

// ═══════════════════════════════════════════════════════════════════
// 05 创新与应用
// ═══════════════════════════════════════════════════════════════════
chapterSlide(pres, 5, "创新与应用", "核心创新点与应用落地价值");

// Slide 05-A: 创新点
{
  let s = pres.addSlide();
  slideHeader(s, pres, 5, "创新与应用", "七大核心创新点");

  const innovations = [
    { num: "01", title: "Text-to-SQL 与政策审查深度融合", desc: "SQL不再是查询工具，而是政策证据引擎，结果直接进入审查链路" },
    { num: "02", title: "证据卡片机制", desc: "统一EvidenceItem结构，使智能体推理边界明确，前端展示直观，审计可追溯" },
    { num: "03", title: "SQL 自动修复链路", desc: "首次匹配率62.5%→修复后87.5%，+22.5个百分点，显著提升取证鲁棒性" },
    { num: "04", title: "多角色辩论增强决策", desc: "六类角色模拟审核委员会，理由完整率91.67%，冲突识别率100%" },
    { num: "05", title: "证据约束抑制幻觉", desc: "去证据约束后准确率12.5%→完整链路87.5%，实验量化证明约束价值" },
    { num: "06", title: "人机协同复核闭环", desc: "「机器初审+人工补证+再裁决」，机器辅助而不替代，满足合规要求" },
    { num: "07", title: "流式交互体验", desc: "SSE逐步推送进度，用户实时看到取证→辩论→裁决全过程，无黑盒感" },
  ];

  innovations.forEach((inn, i) => {
    const col = i < 4 ? 0 : 1;
    const row = i < 4 ? i : i - 4;
    const x = 0.3 + col * 4.9;
    const y = 0.72 + row * 1.15;
    addCard(s, pres, x, y, 4.65, 1.0, { fill: C.white });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.5, h: 1.0, fill: { color: C.darkBg }, line: { color: C.darkBg } });
    s.addText(inn.num, { x, y, w: 0.5, h: 1.0, fontSize: 14, bold: true, color: C.accent, align: "center", valign: "middle", fontFace: "Arial Black", margin: 0 });
    s.addText(inn.title, { x: x + 0.6, y: y + 0.06, w: 3.95, h: 0.4, fontSize: 12, bold: true, color: C.darkBg, fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(inn.desc, { x: x + 0.6, y: y + 0.48, w: 3.95, h: 0.45, fontSize: 10, color: "445566", fontFace: "Microsoft YaHei", margin: 0 });
  });
}

// Slide 05-B: 应用价值与展望
{
  let s = pres.addSlide();
  slideHeader(s, pres, 5, "创新与应用", "应用场景与推广价值");

  // Left col: scenarios
  addCard(s, pres, 0.3, 0.72, 4.5, 4.6, { fill: C.white });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.72, w: 4.5, h: 0.48, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("📍  核心应用场景", { x: 0.4, y: 0.72, w: 4.3, h: 0.48, fontSize: 14, bold: true, color: C.white, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  const scenarios = [
    ["灵活就业社保补贴认定", "自动核验参保状态、就业形式、年龄等多维度条件"],
    ["企业社保补贴资格审查", "批量筛查符合条件企业，辅助经办人员初审决策"],
    ["低收入人员政策主动推送", "系统主动识别符合补贴条件人群，推送办理提醒"],
    ["政务审核结果存档管理", "自动生成带证据链的可追溯审查报告，满足留痕要求"],
  ];
  scenarios.forEach((sc, i) => {
    s.addShape(pres.shapes.OVAL, { x: 0.45, y: 1.35 + i * 0.93, w: 0.25, h: 0.25, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(sc[0], { x: 0.82, y: 1.3 + i * 0.93, w: 3.8, h: 0.38, fontSize: 12, bold: true, color: C.darkBg, fontFace: "Microsoft YaHei", margin: 0 });
    s.addText(sc[1], { x: 0.82, y: 1.68 + i * 0.93, w: 3.8, h: 0.38, fontSize: 10.5, color: "445566", fontFace: "Microsoft YaHei", margin: 0 });
  });

  // Right col: value + future
  addCard(s, pres, 5.0, 0.72, 4.7, 2.1, { fill: C.white });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.0, y: 0.72, w: 4.7, h: 0.48, fill: { color: C.teal }, line: { color: C.teal } });
  s.addText("🌐  推广与扩展价值", { x: 5.1, y: 0.72, w: 4.5, h: 0.48, fontSize: 14, bold: true, color: C.white, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  const vals = [
    "政策文件可替换 → 快速迁移至其他政策场景",
    "业务数据库可接入 → 适配不同城市数据格式",
    "智能体角色可配置 → 按业务需求调整辩论策略",
    "系统架构前后端分离 → 易于对接现有政务系统",
  ];
  vals.forEach((v, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.3 + i * 0.38, w: 0.15, h: 0.28, fill: { color: C.teal }, line: { color: C.teal } });
    s.addText(v, { x: 5.35, y: 1.28 + i * 0.38, w: 4.2, h: 0.35, fontSize: 11, color: "334455", fontFace: "Microsoft YaHei", margin: 0 });
  });

  addCard(s, pres, 5.0, 3.0, 4.7, 2.3, { fill: C.white });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.0, y: 3.0, w: 4.7, h: 0.48, fill: { color: C.accentDim }, line: { color: C.accentDim } });
  s.addText("🔭  未来演进方向", { x: 5.1, y: 3.0, w: 4.5, h: 0.48, fontSize: 14, bold: true, color: C.white, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  const futures = [
    "支持更复杂跨库多跳推理的SQL链路",
    "引入RAG检索增强政策知识库",
    "对接政务API实现实时数据接入",
    "面向市级政务平台规模化落地部署",
  ];
  futures.forEach((f, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.1, y: 3.58 + i * 0.41, w: 4.5, h: 0.34, fill: { color: "FEF9E7" }, line: { color: C.accent, width: 1 }, rectRadius: 0.04 });
    s.addText("→  " + f, { x: 5.2, y: 3.58 + i * 0.41, w: 4.3, h: 0.34, fontSize: 11, color: C.accentDim, valign: "middle", fontFace: "Microsoft YaHei", margin: 0 });
  });
}

// ─── Final: Closing ────────────────────────────────────────────────────────
{
  let s = pres.addSlide();
  s.background = { color: C.darkBg };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent }, line: { color: C.accent } });

  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 1.3, w: 0.08, h: 3.0, fill: { color: C.accent }, line: { color: C.accent } });

  s.addText("谢谢观看", {
    x: 0.9, y: 1.3, w: 8.5, h: 1.0, fontSize: 52, bold: true, color: C.white, fontFace: "Microsoft YaHei", margin: 0
  });
  s.addText("Thank You", {
    x: 0.9, y: 2.35, w: 8.5, h: 0.7, fontSize: 28, color: C.muted, fontFace: "Calibri", italic: true, margin: 0
  });

  s.addText("面向政策资格认定的多智能体辩论式 Text-to-SQL 智能评审系统", {
    x: 0.9, y: 3.15, w: 8.5, h: 0.5, fontSize: 14, color: C.offWhite, fontFace: "Microsoft YaHei", margin: 0
  });

  const summary = [
    "SQL修复机制   62.5% → 87.5%",
    "完整链路质量   91.04 分",
    "证据约束价值   已量化验证",
    "人机协同   可落地部署",
  ];
  summary.forEach((item, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.9 + i * 2.28, y: 3.9, w: 2.1, h: 0.8,
      fill: { color: C.cardBg }, line: { color: C.accent, width: 1 }, rectRadius: 0.05
    });
    s.addText(item, {
      x: 0.9 + i * 2.28, y: 3.9, w: 2.1, h: 0.8,
      fontSize: 10, color: C.accent, align: "center", valign: "middle", fontFace: "Microsoft YaHei", margin: 0
    });
  });

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.57, w: 10, h: 0.055, fill: { color: C.accent }, line: { color: C.accent } });
}

// Write
pres.writeFile({ fileName: "D:/AI/bysj_t2s-master/智能评审系统_PPT.pptx" })
  .then(() => console.log("Done!"))
  .catch(e => console.error(e));

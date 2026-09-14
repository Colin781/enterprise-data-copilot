const services = [
  { name: "Platform API", owner: "身份、租户、任务与审计" },
  { name: "Agent Service", owner: "检索、规划与安全分析工作流" },
  { name: "Web", owner: "用户交互与结构化结果展示" },
];

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">ENTERPRISE DATA COPILOT</p>
        <h1>零售经营分析，从可信边界开始。</h1>
        <p className="summary">
          阶段一正在建立可独立运行的 Java、Python 和 Web 服务骨架。
          业务功能将在后续阶段按可验证的纵向切片逐步加入。
        </p>
        <span className="badge">P1 · Foundation</span>
      </section>

      <section className="services" aria-labelledby="services-title">
        <h2 id="services-title">服务边界</h2>
        <div className="grid">
          {services.map((service) => (
            <article key={service.name}>
              <h3>{service.name}</h3>
              <p>{service.owner}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

import { Link } from 'react-router-dom'
import { LandingNav } from '../components/layout/LandingNav'

const INDICES = [
  { sym: 'NIFTY 50', price: 24832.5, chg: 0.42 },
  { sym: 'BANK NIFTY', price: 52104.2, chg: -0.18 },
  { sym: 'SENSEX', price: 81642.8, chg: 0.31 },
  { sym: 'RELIANCE', price: 1425.6, chg: 0.85 },
]

export function HomePage() {
  return (
    <div className="min-h-screen bg-bg bg-grid bg-grid">
      <LandingNav />

      <section className="max-w-7xl mx-auto px-6 pt-16 pb-24">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-pill bg-accent-50 border border-accent/20 text-accent text-xs font-semibold mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-up animate-pulse" />
              Live Market Intelligence Platform
            </div>
            <h1 className="font-display text-4xl md:text-5xl lg:text-[3.25rem] font-extrabold text-primary-navy leading-[1.1] tracking-tight">
              Institutional-Grade Scalping for Indian Markets
            </h1>
            <p className="text-lg text-text-muted mt-6 leading-relaxed max-w-xl">
              Self-hosted Aladin strategy engine with multi-broker support, multi-timeframe
              confirmation, and production-grade risk management. Built for serious intraday operators.
            </p>
            <div className="flex flex-wrap gap-3 mt-8">
              <Link to="/signup" className="btn-primary px-7 py-3 text-base">
                Get Started Free
                <ArrowIcon />
              </Link>
              <a href="#features" className="btn-secondary px-7 py-3 text-base">Explore Features</a>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mt-14 pt-8 border-t border-border">
              {[
                { v: 'MTF', l: 'Confirmation' },
                { v: '<60s', l: 'Signal Loop' },
                { v: '100%', l: 'Paper First' },
                { v: '24/7', l: 'Self-Hosted' },
              ].map((s) => (
                <div key={s.l}>
                  <p className="font-display text-2xl font-bold text-primary-navy">{s.v}</p>
                  <p className="text-xs text-text-muted mt-0.5">{s.l}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-6 shadow-elevated">
            <div className="flex items-center justify-between mb-5">
              <span className="text-xs font-bold uppercase tracking-wider text-text-faint">Live Market Feed</span>
              <span className="badge bg-accent-50 text-accent">
                <span className="w-1.5 h-1.5 rounded-full bg-up mr-1.5 inline-block" />
                LIVE
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {INDICES.map((t) => {
                const up = t.chg >= 0
                return (
                  <div
                    key={t.sym}
                    className={`rounded-btn border p-4 ${up ? 'border-up/20 bg-accent-50/50' : 'border-down/20 bg-down/5'}`}
                  >
                    <p className="text-xs font-semibold text-text-faint">{t.sym}</p>
                    <p className="text-xl font-bold tabular-nums mt-1">₹{t.price.toLocaleString('en-IN')}</p>
                    <p className={`text-sm font-semibold mt-0.5 ${up ? 'text-up' : 'text-down'}`}>
                      {up ? '+' : ''}{t.chg}%
                    </p>
                  </div>
                )
              })}
            </div>
            <div className="mt-4 p-3 rounded-btn bg-primary-50 border border-primary/10 text-sm">
              <span className="text-primary font-semibold">Aladin</span>
              <span className="text-text-muted"> — RSI crossover signal detected on RELIANCE 5m</span>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="bg-surface border-y border-border py-20">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="font-display text-3xl font-bold text-primary-navy text-center mb-4">Why ScalpDesk</h2>
          <p className="text-text-muted text-center max-w-2xl mx-auto mb-12">
            Everything you need to run a disciplined scalping operation — from signal to execution to risk controls.
          </p>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { title: 'Aladin Engine', desc: 'RSI + WMA + EMA crossover with higher-timeframe trend confirmation and anti-chase filters.' },
              { title: 'Multi-Account Fan-Out', desc: 'One signal, many accounts. Isolated failure handling so one reject never blocks the fleet.' },
              { title: 'Risk Guards', desc: 'Daily max loss, trade limits, consecutive-loss pause, and a one-click global kill switch.' },
            ].map((f) => (
              <div key={f.title} className="card p-6 hover:shadow-elevated transition-shadow">
                <div className="w-10 h-10 rounded-btn bg-primary-50 flex items-center justify-center mb-4">
                  <svg className="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
                <p className="text-sm text-text-muted leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="technology" className="py-20">
        <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="font-display text-3xl font-bold text-primary-navy mb-4">Built for Production</h2>
            <p className="text-text-muted leading-relaxed mb-6">
              FastAPI backend with async PostgreSQL, Redis pub/sub for live ticks, APScheduler for morning login
              and EOD square-off. React terminal with TradingView Lightweight Charts.
            </p>
            <ul className="space-y-3">
              {['Kite Connect REST + WebSocket', 'Encrypted broker credentials at rest', 'Full audit log & P&L dashboard', 'Paper mode by default'].map((item) => (
                <li key={item} className="flex items-center gap-2 text-sm">
                  <CheckIcon />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="card p-6 font-mono text-xs text-text-muted space-y-2 bg-primary-navy text-white/80">
            <p><span className="text-accent">strategy</span> → pre-checks → regime filter → signal</p>
            <p><span className="text-accent">         </span> → MTF confirm → sizing → bracket order</p>
            <p><span className="text-accent">         </span> → manage → partial → trail → EOD exit</p>
          </div>
        </div>
      </section>

      <section id="risk" className="bg-primary-navy text-white py-16">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="font-display text-2xl font-bold mb-4">Safety First — Always Paper Mode</h2>
          <p className="text-white/70 leading-relaxed">
            Every strategy starts in paper mode. Validate on one account before going live.
            Zerodha requires manual login once per trading day. This platform is for your own accounts only.
          </p>
          <Link to="/signup" className="inline-flex mt-8 btn-accent px-8 py-3">Create Your Terminal</Link>
        </div>
      </section>

      <footer className="border-t border-border py-8 text-center text-sm text-text-faint">
        ScalpDesk — Self-hosted scalping platform. Not financial advice.
      </footer>
    </div>
  )
}

function ArrowIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4 text-up shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

import './HomePage.css'

const GAMES = [
  {
    id: 'ttt',
    name: 'Tic-Tac-Toe',
    tagline: 'The classic three-in-a-row showdown',
    symbol: '#',
    theme: 'purple',
    available: true,
  },
  {
    id: 'chess',
    name: 'Chess',
    tagline: 'Royal strategy at its finest',
    symbol: '♛',
    theme: 'blue',
    available: false,
  },
  {
    id: 'connect4',
    name: 'Connect Four',
    tagline: 'Drop pieces and dominate the board',
    symbol: '◉',
    theme: 'red',
    available: false,
  },
  {
    id: 'word',
    name: 'Word Duel',
    tagline: 'Spell your way to victory',
    symbol: 'A',
    theme: 'green',
    available: false,
  },
  {
    id: 'numbers',
    name: 'Number Clash',
    tagline: 'Crunch numbers, crush your opponent',
    symbol: '∑',
    theme: 'amber',
    available: false,
  },
  {
    id: 'rps',
    name: 'Rock Paper Scissors',
    tagline: 'Luck, bluff, and split-second choices',
    symbol: '✌',
    theme: 'pink',
    available: false,
  },
]

function GameCard({ name, tagline, symbol, theme, available }) {
  return (
    <article className={`game-card card-${theme}`}>
      <div className="card-icon-ring">
        <span className="card-symbol">{symbol}</span>
      </div>
      <div className="card-body">
        <h3 className="card-name">{name}</h3>
        <p className="card-tagline">{tagline}</p>
      </div>
      <div className="card-footer">
        {available ? (
          <button className="play-btn">
            Play Now
            <span className="btn-arrow" aria-hidden="true">→</span>
          </button>
        ) : (
          <span className="soon-chip">Coming Soon</span>
        )}
      </div>
    </article>
  )
}

export default function HomePage() {
  return (
    <div className="homepage">
      <div className="bg-layer" aria-hidden="true">
        <div className="crosses-layer" />
        <div className="blob blob-1" />
        <div className="blob blob-2" />
        <div className="blob blob-3" />
        <div className="blob blob-4" />
        <div className="blob blob-5" />
        <div className="blob blob-6" />
      </div>

      <header className="hero">
        <div className="hero-glow" />
        <div className="logo-wrap">
          <h1 className="logo-versus">VERSUS</h1>
          <p className="logo-games">GAMES</p>
        </div>
        <p className="hero-tagline">Pick a game. Pick a side. Prove yourself.</p>
      </header>

      <main className="games-section">
        <h2 className="section-heading">Choose Your Battle</h2>
        <div className="games-grid">
          {GAMES.map((game) => (
            <GameCard key={game.id} {...game} />
          ))}
        </div>
      </main>

      <footer className="site-footer">
        <p>© 2025 Versus Games — More games arriving soon!</p>
      </footer>
    </div>
  )
}

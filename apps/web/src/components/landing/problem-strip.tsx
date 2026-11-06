import { Container } from "./primitives";

const COLUMNS = 50;
const ROWS = 10;
const CELL = 10;

/** Five acted-on saves, scattered among the 500. Positions are [column, row]. */
const actedOn = [
  [7, 2],
  [18, 7],
  [26, 1],
  [38, 5],
  [45, 8],
];

/**
 * 500 dots, drawn with an SVG pattern so the page carries one shape rather than
 * 500 DOM nodes.
 */
function SavedDots() {
  return (
    <svg
      viewBox={`0 0 ${COLUMNS * CELL} ${ROWS * CELL}`}
      role="img"
      aria-label="A grid of 500 dots, one for each save. Only 5 are highlighted."
      className="w-full"
    >
      <defs>
        <pattern id="saved-dot" width={CELL} height={CELL} patternUnits="userSpaceOnUse">
          <circle cx={CELL / 2} cy={CELL / 2} r="2.2" className="fill-muted-foreground/30" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#saved-dot)" />
      {actedOn.map(([column, row]) => (
        <circle
          key={`${column}-${row}`}
          cx={column * CELL + CELL / 2}
          cy={row * CELL + CELL / 2}
          r="3.6"
          className="fill-primary"
        />
      ))}
    </svg>
  );
}

export function ProblemStrip() {
  return (
    <section aria-label="The problem" className="border-y bg-muted/40">
      <Container className="py-16 sm:py-20">
        <div className="reveal grid grid-cols-1 items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:gap-16">
          <p className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            You&apos;ve saved 500 things.{" "}
            <span className="text-muted-foreground">You&apos;ve acted on 5.</span>
          </p>
          <div>
            <SavedDots />
            <p className="mt-4 text-sm text-pretty text-muted-foreground">
              Saving feels like progress. Most tools make it easier to hoard, and none of them ask
              what happened next.
            </p>
          </div>
        </div>
      </Container>
    </section>
  );
}

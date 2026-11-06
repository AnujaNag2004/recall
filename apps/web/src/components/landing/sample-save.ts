/**
 * The one example save used across the landing page, so the hero, the showcase
 * and the follow-up loop all tell the same story: Priya, a student, saved a video.
 * The video is invented. The named resources are real sites and a real book.
 */
export const sampleSave = {
  url: "youtube.com/watch?v=graphs-in-15",
  title: "Graph algorithms in 15 minutes",
  source: "YouTube · 15:02",
  mode: "Study",
  intent: "Learn",
  summary:
    "A fast tour of BFS, DFS and Dijkstra: when each one fits, and how to spot a graph hiding inside an ordinary interview problem.",
  keyPoints: [
    "BFS finds shortest paths when every edge costs the same.",
    "DFS suits cycle detection and exhaustive search.",
    "Dijkstra handles weighted edges, as long as none are negative.",
  ],
  transcript: [
    { at: 12, text: "Most interview problems about grids are really graph problems." },
    { at: 192, text: "VisuAlgo lets you step through BFS one node at a time." },
    { at: 425, text: "The chapter on graphs in CLRS is the reference to keep around." },
    { at: 700, text: "Solve one problem on LeetCode tonight while this is still fresh." },
  ],
  resources: [
    {
      name: "VisuAlgo",
      domain: "visualgo.net",
      note: "Step-through algorithm visualizations",
      pricing: "Free",
      confidence: 0.97,
      at: 192,
      verified: true,
    },
    {
      name: "Introduction to Algorithms",
      domain: "mitpress.mit.edu",
      note: "The CLRS textbook, mentioned for its graphs chapter",
      pricing: "Paid",
      confidence: 0.91,
      at: 425,
      verified: true,
    },
    {
      name: "LeetCode",
      domain: "leetcode.com",
      note: "Practice problems, with a graph topic list",
      pricing: "Freemium",
      confidence: 0.95,
      at: 700,
      verified: true,
    },
    {
      name: "“the graph playground”",
      domain: null,
      note: "Mentioned in passing. No official link could be confirmed.",
      pricing: "Unknown",
      confidence: 0.41,
      at: 512,
      verified: false,
    },
  ],
  actions: [
    { title: "Solve 1 graph problem", detail: "Tonight, 9:00 pm · 15 min", micro: true },
    { title: "Step through BFS on VisuAlgo", detail: "Tomorrow · 5 min", micro: false },
    { title: "Review 6 generated flashcards", detail: "Saturday · 10 min", micro: false },
  ],
};

export function formatTimestamp(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

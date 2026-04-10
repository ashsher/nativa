/**
 * recommendations.js — Curated starter content for new users.
 *
 * Provides 20 beginner-friendly YouTube videos and 20 Simple English Wikipedia
 * articles. Clicking a video card auto-fills the URL input and submits it;
 * clicking an article card does the same for the reading input.
 */

/** @type {Array<{url:string, title:string, channel:string, genre:string, badge?:string}>} */
const RECOMMENDED_VIDEOS = [
  {
    url: 'https://www.youtube.com/watch?v=jNQXAC9IVRw',
    title: 'Me at the zoo',
    channel: 'Jawed Karim',
    genre: 'Tarixiy',
    badge: "YouTube'dagi birinchi video",
  },
  {
    url: 'https://www.youtube.com/watch?v=iG9CE55wbtY',
    title: 'Do schools kill creativity?',
    channel: 'TED',
    genre: 'Ta\'lim',
  },
  {
    url: 'https://www.youtube.com/watch?v=eIho2S0ZahI',
    title: 'How to speak so that people want to listen',
    channel: 'TED',
    genre: 'Muloqot',
  },
  {
    url: 'https://www.youtube.com/watch?v=arj7oStGLkU',
    title: 'Inside the mind of a master procrastinator',
    channel: 'TED',
    genre: 'Psixologiya',
  },
  {
    url: 'https://www.youtube.com/watch?v=UT2UEj9jeN8',
    title: 'What makes a good life? Lessons from the longest study on happiness',
    channel: 'TED',
    genre: 'Hayot',
  },
  {
    url: 'https://www.youtube.com/watch?v=GXy__kBVq1M',
    title: 'The happy secret to better work',
    channel: 'TED',
    genre: 'Psixologiya',
  },
  {
    url: 'https://www.youtube.com/watch?v=Unzc731iCUY',
    title: 'Your body language may shape who you are',
    channel: 'TED',
    genre: 'Psixologiya',
  },
  {
    url: 'https://www.youtube.com/watch?v=H14bBuluwB8',
    title: 'Grit: the power of passion and perseverance',
    channel: 'TED',
    genre: 'Motivatsiya',
  },
  {
    url: 'https://www.youtube.com/watch?v=qp0HIF3SfI4',
    title: 'How great leaders inspire action',
    channel: 'TED',
    genre: 'Liderlik',
  },
  {
    url: 'https://www.youtube.com/watch?v=iCvmsMzlF7o',
    title: 'The surprising science of happiness',
    channel: 'TED',
    genre: 'Psixologiya',
  },
  {
    url: 'https://www.youtube.com/watch?v=d4KisFBRtnE',
    title: 'The power of vulnerability',
    channel: 'TED',
    genre: 'Hayot',
  },
  {
    url: 'https://www.youtube.com/watch?v=h6fcK_fRYaI',
    title: 'The Egg — A Short Story',
    channel: 'Kurzgesagt',
    genre: 'Falsafa',
  },
  {
    url: 'https://www.youtube.com/watch?v=MBRqu0YOH14',
    title: 'Optimistic Nihilism',
    channel: 'Kurzgesagt',
    genre: 'Falsafa',
  },
  {
    url: 'https://www.youtube.com/watch?v=QOCaacO8wus',
    title: 'What Is Life? Is Death Real?',
    channel: 'Kurzgesagt',
    genre: 'Fan',
  },
  {
    url: 'https://www.youtube.com/watch?v=NjnQ7cgnCz0',
    title: 'Dear Future Generations: Sorry',
    channel: 'Prince Ea',
    genre: 'Motivatsiya',
  },
  {
    url: 'https://www.youtube.com/watch?v=LnJwH_PZXnM',
    title: 'Why do we Dream?',
    channel: 'Stated Clearly',
    genre: 'Fan',
  },
  {
    url: 'https://www.youtube.com/watch?v=4TYv2PhG89A',
    title: 'The Philosophy of Stoicism',
    channel: 'Einzelgänger',
    genre: 'Falsafa',
  },
  {
    url: 'https://www.youtube.com/watch?v=RKK7wGAYP6k',
    title: 'How language shapes the way we think',
    channel: 'TED',
    genre: 'Til',
  },
  {
    url: 'https://www.youtube.com/watch?v=Lp7E973zozc',
    title: 'How to stop screwing yourself over',
    channel: 'TEDx',
    genre: 'Motivatsiya',
  },
  {
    url: 'https://www.youtube.com/watch?v=-KbKyKzBXLM',
    title: 'The influential mind: what the brain is really telling us',
    channel: 'TED',
    genre: 'Fan',
  },
];

/** @type {Array<{url:string, title:string, category:string}>} */
const RECOMMENDED_ARTICLES = [
  { url: 'https://simple.wikipedia.org/wiki/Dog',                title: 'Dog',               category: 'Hayvonlar'   },
  { url: 'https://simple.wikipedia.org/wiki/Cat',                title: 'Cat',               category: 'Hayvonlar'   },
  { url: 'https://simple.wikipedia.org/wiki/Coffee',             title: 'Coffee',            category: 'Oziq-ovqat'  },
  { url: 'https://simple.wikipedia.org/wiki/Internet',           title: 'Internet',          category: 'Texnologiya' },
  { url: 'https://simple.wikipedia.org/wiki/Music',              title: 'Music',             category: 'San\'at'     },
  { url: 'https://simple.wikipedia.org/wiki/Football',           title: 'Football',          category: 'Sport'       },
  { url: 'https://simple.wikipedia.org/wiki/Pizza',              title: 'Pizza',             category: 'Oziq-ovqat'  },
  { url: 'https://simple.wikipedia.org/wiki/Money',              title: 'Money',             category: 'Iqtisod'     },
  { url: 'https://simple.wikipedia.org/wiki/Moon',               title: 'Moon',              category: 'Fan'         },
  { url: 'https://simple.wikipedia.org/wiki/Sun',                title: 'Sun',               category: 'Fan'         },
  { url: 'https://simple.wikipedia.org/wiki/Artificial_intelligence', title: 'Artificial Intelligence', category: 'Texnologiya' },
  { url: 'https://simple.wikipedia.org/wiki/Water',              title: 'Water',             category: 'Fan'         },
  { url: 'https://simple.wikipedia.org/wiki/Apple_Inc.',         title: 'Apple Inc.',        category: 'Texnologiya' },
  { url: 'https://simple.wikipedia.org/wiki/English_language',   title: 'English Language',  category: 'Til'         },
  { url: 'https://simple.wikipedia.org/wiki/Book',               title: 'Book',              category: 'Madaniyat'   },
  { url: 'https://simple.wikipedia.org/wiki/Computer',           title: 'Computer',          category: 'Texnologiya' },
  { url: 'https://simple.wikipedia.org/wiki/Earth',              title: 'Earth',             category: 'Fan'         },
  { url: 'https://simple.wikipedia.org/wiki/Health',             title: 'Health',            category: 'Sog\'liq'    },
  { url: 'https://simple.wikipedia.org/wiki/Time',               title: 'Time',              category: 'Fan'         },
  { url: 'https://simple.wikipedia.org/wiki/Uzbekistan',         title: 'Uzbekistan',        category: 'Geografiya'  },
];

/* ─────────────────────────────────────────────────────────────────────────────
   VIDEO RECOMMENDATIONS
   Horizontal scroll rail inside the video input state.
───────────────────────────────────────────────────────────────────────────── */

/**
 * renderRecommendedVideos — builds the horizontal card rail and injects it
 * after the input group inside .video-input-state.
 */
function renderRecommendedVideos() {
  const container = document.getElementById('recommended-videos');
  if (!container) return;

  const heading = document.createElement('p');
  heading.className = 'rec-section-label';
  heading.textContent = 'Tavsiya etilgan videolar';
  container.appendChild(heading);

  const rail = document.createElement('div');
  rail.className = 'rec-video-rail';

  RECOMMENDED_VIDEOS.forEach(video => {
    const card = document.createElement('div');
    card.className = 'rec-video-card';
    card.title = video.title;

    // Genre chip + optional badge
    const meta = document.createElement('div');
    meta.className = 'rec-video-meta';

    const genreChip = document.createElement('span');
    genreChip.className = 'rec-genre-chip';
    genreChip.textContent = video.genre;
    meta.appendChild(genreChip);

    if (video.badge) {
      const badgeEl = document.createElement('span');
      badgeEl.className = 'rec-badge';
      badgeEl.textContent = video.badge;
      meta.appendChild(badgeEl);
    }

    // Title
    const titleEl = document.createElement('div');
    titleEl.className = 'rec-video-title';
    titleEl.textContent = video.title;

    // Channel
    const channelEl = document.createElement('div');
    channelEl.className = 'rec-video-channel';
    channelEl.textContent = video.channel;

    card.appendChild(meta);
    card.appendChild(titleEl);
    card.appendChild(channelEl);

    // Click → fill URL input and auto-submit
    card.addEventListener('click', () => {
      const urlInput = document.getElementById('video-url-input');
      if (urlInput) urlInput.value = video.url;
      if (typeof submitVideoURL === 'function') {
        submitVideoURL(video.url);
      } else {
        document.getElementById('video-submit-btn')?.click();
      }
    });

    rail.appendChild(card);
  });

  container.appendChild(rail);
}

/* ─────────────────────────────────────────────────────────────────────────────
   ARTICLE RECOMMENDATIONS
   Two-column grid inside the reading input state.
───────────────────────────────────────────────────────────────────────────── */

/**
 * renderRecommendedArticles — builds the 2-column article grid and injects it
 * after the submit button inside .reading-input-state.
 */
function renderRecommendedArticles() {
  const container = document.getElementById('recommended-articles');
  if (!container) return;

  const heading = document.createElement('p');
  heading.className = 'rec-section-label';
  heading.textContent = 'Tavsiya etilgan maqolalar';
  container.appendChild(heading);

  const grid = document.createElement('div');
  grid.className = 'rec-article-grid';

  RECOMMENDED_ARTICLES.forEach(article => {
    const card = document.createElement('div');
    card.className = 'rec-article-card';

    const catEl = document.createElement('div');
    catEl.className = 'rec-article-cat';
    catEl.textContent = article.category;

    const titleEl = document.createElement('div');
    titleEl.className = 'rec-article-title';
    titleEl.textContent = article.title;

    card.appendChild(catEl);
    card.appendChild(titleEl);

    // Click → fill URL input (switch to URL mode if needed) and auto-submit
    card.addEventListener('click', () => {
      // Ensure URL mode is active
      const urlTab = document.getElementById('reading-tab-url');
      if (urlTab && !urlTab.classList.contains('pill-toggle__btn--active')) {
        urlTab.click();
      }
      const urlInput = document.getElementById('reading-url-input');
      if (urlInput) urlInput.value = article.url;
      if (typeof submitReading === 'function') {
        submitReading();
      } else {
        document.getElementById('reading-submit-btn')?.click();
      }
    });

    grid.appendChild(card);
  });

  container.appendChild(grid);
}

/* ─────────────────────────────────────────────────────────────────────────────
   INIT — run once the DOM is ready
───────────────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderRecommendedVideos();
  renderRecommendedArticles();
});

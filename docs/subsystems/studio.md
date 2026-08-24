# Subsystem — Studio (music + art)

> **Status: built.** The route and media components are implemented; add assets as the portfolio grows.

## What this will own

The creative hub at `/studio`: music and art presented on the site's dark canvas with large,
media-forward layouts. Color comes from the media, not the chrome (see
[reference/design-system.md](../reference/design-system.md)).

## Planned shape

- `app/studio/page.tsx` — the hub (music + art sections).
- `components/studio/MusicPlayer.tsx` — third-party embeds (SoundCloud/Spotify/Bandcamp) or a
  self-hosted player over files in `public/audio/`.
- `components/studio/ArtGallery.tsx` — image galleries with a lightbox, served from
  `public/art/` via `next/image`.

## Open decision

Music hosting — third-party embeds vs self-hosted audio — is still open (plan §14). Document
the choice here when made.

## Invariants it must respect

- [Static-first](../concepts/static-first.md): media is static assets / embeds; no backend.
- [Read-only](../concepts/public-site-is-read-only.md).

## To fill this in

Replace this stub when `/studio` exists. Document the media sources, the gallery/lightbox
behaviour, and image-optimization conventions.

## Source files

- `app/studio/page.tsx`, `components/studio/*`, `public/art/`, `public/audio/`.

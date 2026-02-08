# Avatar Directory

This directory contains avatar images that users can choose from during onboarding and profile editing.

## Avatar Naming Pattern

Avatars must follow this naming convention:
```
[MBTI]-[gender].png
```

Where:
- **MBTI** is one of the 16 Myers-Briggs Type Indicator types: `INTJ`, `INTP`, `ENTJ`, `ENTP`, `INFJ`, `INFP`, `ENFJ`, `ENFP`, `ISTJ`, `ISFJ`, `ESTJ`, `ESFJ`, `ISTP`, `ISFP`, `ESTP`, `ESFP`
- **gender** is either `w` (woman) or `m` (man)

## Examples

- `INTJ-w.png` - INTJ personality, woman
- `ENFP-m.png` - ENFP personality, man
- `ISTJ-w.png` - ISTJ personality, woman

## Adding Avatars

To add avatar images:

1. Place image files (PNG format recommended) in this directory
2. Name them following the pattern: `[MBTI]-[gender].png`
3. Recommended size: 200x200 pixels or larger (square aspect ratio)
4. Supported formats: PNG, JPG, SVG

## Current Avatar List

The app will automatically detect all avatars that match the naming pattern. Currently available:
- `entj-w.png`
- `entp-w.png`
- `infj-w.png`
- `intj-w.png`
- `intp-w.png`

## Avatar Picker Features

The avatar picker will:
- Automatically discover all avatars matching the pattern
- Group avatars by MBTI type
- Filter by gender (All/Woman/Man)
- Display gender labels on each avatar
- Show only avatars that actually exist in the directory

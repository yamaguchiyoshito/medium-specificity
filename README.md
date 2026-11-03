# 媒体固有性で読む九つの芸術

## 建築から漫画まで、芸術を媒体の条件から読み解く、全10回

**芸術の固有性は、媒体の条件と制約から生まれる。**

写真が登場したあと、絵画はなぜ抽象へ向かったのか。この連載は、Medium Specificity（媒体固有性）という美学理論を軸に、各芸術が「何でできていて、何ができて、何ができないのか」を順に読み解く。第1回で概念と系譜を整理し、第2〜9回で建築・彫刻から漫画までの九つの芸術を見て、第10回でデジタル時代の現在地を考える。各回は独立した読み物であり、末尾の一段落が次回へつながる。

[第1回から読む](chapters/01-what-is-medium-specificity.md) ／ [最終回を読む](chapters/10-post-medium.md) ／ [読み方](guides/READING.md)

## 全10回の目次

| 回 | 文章 | 主題 |
| --- | --- | --- |
| 01 | [媒体固有性とは何か](chapters/01-what-is-medium-specificity.md) | 概念定義、レッシングからグリーンバーグへ、制約の逆説 |
| 02 | [建築と彫刻——住めるか、眺めるか](chapters/02-architecture-and-sculpture.md) | 重力と居住可能性、量塊と空虚、台座の消失 |
| 03 | [絵画——窓から壁へ](chapters/03-painting.md) | 平面性、支持体と顔料、写真との競争 |
| 04 | [音楽——時間の中にしかないもの](chapters/04-music.md) | 純粋な時間芸術、沈黙、旋律・和声・リズム |
| 05 | [文学——言語だけでできた世界](chapters/05-literature.md) | 言語記号、内面描写、語りの視点 |
| 06 | [舞台芸術——今ここに身体がある](chapters/06-performing-arts.md) | 現前、一回性、観客との相互作用 |
| 07 | [映画——編集がつくる時間](chapters/07-cinema.md) | モンタージュ、運動の錯視、音響設計 |
| 08 | [写真——光の痕跡と瞬間の切断](chapters/08-photography.md) | インデックス性、フレーミング、デジタルとAI |
| 09 | [漫画——時間を空間に並べる](chapters/09-comics.md) | コマ、クロージャー、読者の時間制御 |
| 10 | [ポストメディウム以後の媒体固有性](chapters/10-post-medium.md) | クラウスの再定義、デジタル収斂、理論の現在地 |

## 連載の構成

第I部「理論を知る」（1回）は、媒体固有性の定義と系譜、制約が創造を決めるという逆説を整理し、以降の読み方を示す。第II部「空間と物質の芸術」（2〜3回）は、重力に縛られる建築、実体として眺められる彫刻、平面を条件とする絵画を扱う。第III部「時間と言語の芸術」（4〜6回）は、時間の中にだけ存在する音楽、言語記号だけの文学、身体の現前を条件とする舞台芸術を扱う。第IV部「技術が支える芸術」（7〜9回）は、編集の映画、光の痕跡の写真、コマの漫画を扱う。第V部「現在地」（10回）は、デジタル収斂のもとで、理論がどこまで有効かを考える。

各回は、媒体固有の条件、固有の表現領域、他芸術との境界という三つの視点で進む。建築と彫刻は境界の問題が結びついているため、第2回にまとめた。第8回は、第8芸術「写真・テレビ・ラジオ」のうち写真だけを扱い、テレビとラジオは範囲に含めない。

本連載には、理論の紹介と、各芸術の整理や作例の読みが混ざっている。断定的に見える箇所も、定説というより一つの読みとして扱う。「第9芸術」などの番号は、フランス語圏の慣習による呼び名であり、芸術に優劣をつけるものではない。

<!-- SITE-INDEX-END: 以下はリポジトリ利用者向け。HTML閲覧版のトップページには含めない。 -->

## GitHubで読む

このREADMEと各回の `.md` をGitHubの **Preview** で開く。

## ブラウザで読む（GitHub Pages）

公開ページは https://yamaguchiyoshito.github.io/medium-specificity/ にする想定である（リポジトリ名を `medium-specificity` とした場合）。`main` ブランチへのpushで `.github/workflows/pages.yml` が `_site/` を生成し、GitHub Pagesへ配置する。有効にするにはリポジトリの Settings → Pages → Build and deployment で Source を **GitHub Actions** にする。

ローカルで再生成するにはPython 3.11以降とPandoc 3.xを使う。依存パッケージの追加インストールは不要である。

```sh
python scripts/validate.py
python scripts/build.py
python -m unittest discover -s tests -v
```

`_site/index.html` が目次付きの閲覧ページ、`_site/complete.html` が全10回を一つにまとめた単独ファイルである。GitHub管理対象はMarkdownなどの原本であり、`_site/` は生成物として `.gitignore` で除外する。

## 連載の成り立ちと編集

媒体固有性の解説文書を元に、全10回の連載として再構成した。各回の題名・副題・前後リンクの型を揃え、閲覧サイトの仕組みは、連載[『意識の再定義』](https://github.com/yamaguchiyoshito/consciousness-as-computation)と同じ構成にしている。[編集ガイド](guides/EDITING.md)に原本と生成物の責務を、[読み方](guides/READING.md)に表示環境の注意をまとめた。変更履歴は[CHANGELOG](CHANGELOG.md)にある。変更はブランチを切ってPull Requestで取り込む。

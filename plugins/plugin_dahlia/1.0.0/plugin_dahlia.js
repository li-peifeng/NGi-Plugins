/* NGi-provider
{"api_version":1,"id":"plugin_dahlia","name":"DAHLIA","version":"1.0.0","base_url":"https://dahlia-av.jp","description":"DAHLIA 官方作品、海报与剧照","categories":["jav_censored"]}
*/
const site = {prefix:'',studio:'DAHLIA',publisher:'DAHLIA',labels:{}};
const workSlug = /^([a-z]+)(\d+)([a-z]*)$/;

function slugFromNumber(number) {
  const slug = number.toLowerCase().replace(/[-_\s]/g, '');
  return workSlug.test(slug) ? slug : '';
}

function displayNumber(slug) {
  const parts = workSlug.exec(slug);
  return `${parts[1].toUpperCase()}-${parts[2]}${parts[3].toUpperCase()}`;
}

async function getWork(ctx, slug) {
  const posts = await ctx.http.json(`${site.prefix}/wp-json/wp/v2/works?slug=${slug}`);
  if (!Array.isArray(posts)) throw new Error('官网作品接口返回格式错误');
  const matches = posts.filter(post => typeof post?.slug === 'string' && post.slug.toLowerCase() === slug);
  return matches.length === 1 ? matches[0] : null;
}

function plainText(ctx, value) {
  if (typeof value !== 'string') return '';
  if (!/[<&]/.test(value)) return value.trim();
  return ctx.html.parse(`<div id="field">${value}</div>`).select('#field').text().trim();
}

function releaseDate(value) {
  const match = /^(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?$/.exec(value.trim());
  if (!match) return '';
  return `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;
}

export default {
  async search(ctx, number) {
    const slug = slugFromNumber(number);
    if (!slug || !await getWork(ctx, slug)) return [];
    return [{number, url: `${site.prefix}/works/${slug}/`}];
  },
  async detail(ctx, url) {
    const path = url.replace(/^https?:\/\/[^/]+/, '').split(/[?#]/, 1)[0];
    const permalink = `${site.prefix}/works/`;
    const endpoint = `${site.prefix}/wp-json/wp/v2/works`;
    const slug = path.startsWith(permalink)
      ? path.slice(permalink.length).replace(/\/$/, '').toLowerCase()
      : path === endpoint ? new RegExp('[?&]slug=([a-z0-9]+)(?:[&#]|$)', 'i').exec(url)?.[1]?.toLowerCase() : '';
    if (!slug || !workSlug.test(slug)) throw new Error('官网作品链接缺少有效番号');
    const post = await getWork(ctx, slug);
    if (!post) throw new Error('官网未找到对应番号的作品');

    const fields = post.acf ?? {};
    const images = post.acf_custom_images ?? {};
    const title = plainText(ctx, fields['作品名']) || plainText(ctx, post.title?.rendered);
    if (!title) throw new Error('官网作品缺少标题');

    const release = plainText(ctx, fields['発売日（表示用）']);
    const runtime = plainText(ctx, fields['収録時間']).match(/\d+/)?.[0] ?? '';
    const actors = plainText(ctx, fields['出演女優']).split(/[/／、\n]+/).map(name => name.trim()).filter(Boolean);
    const publisher = site.labels[workSlug.exec(slug)[1]] ?? site.publisher;
    const gallery = Array.isArray(images.gallery_urls)
      ? [...new Set(images.gallery_urls.filter(url => typeof url === 'string' && url.trim()))]
      : [];
    return {
      Number: displayNumber(slug), Title: title, OriginalTitle: title,
      Actors: actors, OriginalActors: actors, Studio: site.studio, Publisher: publisher,
      Outline: plainText(ctx, fields['作品紹介文']), Release: releaseDate(release), Runtime: runtime,
      Cover: typeof images.main_photo_url === 'string' ? images.main_photo_url.trim() || null : null,
      Poster: typeof images.sub_photo_url === 'string' ? images.sub_photo_url.trim() || null : null,
      ExtraFanart: gallery,
    };
  },
};

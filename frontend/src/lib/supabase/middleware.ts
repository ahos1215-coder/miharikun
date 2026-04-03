import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// 認証不要のパス
const PUBLIC_PATHS = ["/", "/login", "/signup", "/news"];

function isPublic(pathname: string): boolean {
  if (PUBLIC_PATHS.includes(pathname)) return true;
  if (pathname.startsWith("/news/")) return true;
  return false;
}

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // ============================================================
  // 開発モード: 認証リダイレクト一時停止
  // 誰でも全ページ閲覧可能。本番復帰時にこのブロックを元に戻すこと。
  // ============================================================
  // if (!user && !isPublic(request.nextUrl.pathname)) {
  //   const url = request.nextUrl.clone();
  //   url.pathname = "/login";
  //   url.searchParams.set("redirect", request.nextUrl.pathname);
  //   return NextResponse.redirect(url);
  // }
  // if (user && request.nextUrl.pathname === "/login") {
  //   const url = request.nextUrl.clone();
  //   url.pathname = "/dashboard";
  //   return NextResponse.redirect(url);
  // }

  return supabaseResponse;
}

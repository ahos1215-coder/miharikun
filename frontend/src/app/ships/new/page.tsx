"use client";

import { createClient } from "@/lib/supabase/client";
import {
  SHIP_TYPE_LABELS,
  CLASSIFICATION_LABELS,
  NAV_AREA_LABELS,
  ShipType,
  ClassificationSociety,
  NavigationArea,
} from "@/lib/types";
import { useRouter } from "next/navigation";
import { useState } from "react";

const inputClass =
  "mt-1 block w-full rounded border border-zinc-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900";

const shipTypes = Object.keys(SHIP_TYPE_LABELS) as ShipType[];
const classificationSocieties = Object.keys(CLASSIFICATION_LABELS) as ClassificationSociety[];
const navAreas = Object.keys(NAV_AREA_LABELS) as NavigationArea[];

export default function ShipNewPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [shipName, setShipName] = useState("");
  const [shipType, setShipType] = useState<ShipType>("bulk_carrier");
  const [grossTonnage, setGrossTonnage] = useState("");
  const [dwt, setDwt] = useState("");
  const [buildYear, setBuildYear] = useState("");
  const [classificationSociety, setClassificationSociety] =
    useState<ClassificationSociety>("NK");
  const [flagState, setFlagState] = useState("JPN");
  const [navigationArea, setNavigationArea] = useState<NavigationArea[]>([]);
  const [routes, setRoutes] = useState("");
  const [imoNumber, setImoNumber] = useState("");

  function handleNavAreaChange(area: NavigationArea, checked: boolean) {
    setNavigationArea((prev) =>
      checked ? [...prev, area] : prev.filter((a) => a !== area),
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (navigationArea.length === 0) {
      setError("航行区域を1つ以上選択してください");
      return;
    }

    setLoading(true);

    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      setError("ログインが必要です");
      setLoading(false);
      return;
    }

    const { error: insertError } = await supabase
      .from("ship_profiles")
      .insert({
        user_id: user.id,
        ship_name: shipName,
        ship_type: shipType,
        gross_tonnage: parseInt(grossTonnage, 10),
        dwt: dwt ? parseInt(dwt, 10) : null,
        build_year: parseInt(buildYear, 10),
        classification_society: classificationSociety,
        flag_state: flagState,
        navigation_area: navigationArea,
        routes: routes
          ? routes.split(",").map((r) => r.trim()).filter(Boolean)
          : null,
        imo_number: imoNumber || null,
      });

    if (insertError) {
      setError(insertError.message);
      setLoading(false);
      return;
    }

    router.push("/dashboard");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-lg p-4">
      <h1 className="mb-6 text-xl font-bold">[SHIP] 船舶登録</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* 船名 */}
        <div>
          <label htmlFor="ship_name" className="block text-sm font-medium">
            船名 <span className="text-red-500">*</span>
          </label>
          <input
            id="ship_name"
            type="text"
            required
            maxLength={100}
            value={shipName}
            onChange={(e) => setShipName(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* 船種 */}
        <div>
          <label htmlFor="ship_type" className="block text-sm font-medium">
            船種 <span className="text-red-500">*</span>
          </label>
          <select
            id="ship_type"
            value={shipType}
            onChange={(e) => setShipType(e.target.value as ShipType)}
            className={inputClass}
          >
            {shipTypes.map((t) => (
              <option key={t} value={t}>
                {SHIP_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        </div>

        {/* 総トン数 */}
        <div>
          <label htmlFor="gross_tonnage" className="block text-sm font-medium">
            総トン数 (GT) <span className="text-red-500">*</span>
          </label>
          <input
            id="gross_tonnage"
            type="number"
            required
            min={1}
            max={500000}
            step={1}
            value={grossTonnage}
            onChange={(e) => setGrossTonnage(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* 載貨重量トン数 */}
        <div>
          <label htmlFor="dwt" className="block text-sm font-medium">
            載貨重量トン数 (DWT)
          </label>
          <input
            id="dwt"
            type="number"
            min={1}
            max={1000000}
            step={1}
            value={dwt}
            onChange={(e) => setDwt(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* 建造年 */}
        <div>
          <label htmlFor="build_year" className="block text-sm font-medium">
            建造年 <span className="text-red-500">*</span>
          </label>
          <input
            id="build_year"
            type="number"
            required
            min={1900}
            max={2026}
            value={buildYear}
            onChange={(e) => setBuildYear(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* 船級協会 */}
        <div>
          <label
            htmlFor="classification_society"
            className="block text-sm font-medium"
          >
            船級協会 <span className="text-red-500">*</span>
          </label>
          <select
            id="classification_society"
            value={classificationSociety}
            onChange={(e) =>
              setClassificationSociety(
                e.target.value as ClassificationSociety,
              )
            }
            className={inputClass}
          >
            {classificationSocieties.map((c) => (
              <option key={c} value={c}>
                {CLASSIFICATION_LABELS[c]}
              </option>
            ))}
          </select>
        </div>

        {/* 旗国 */}
        <div>
          <label htmlFor="flag_state" className="block text-sm font-medium">
            旗国
          </label>
          <input
            id="flag_state"
            type="text"
            value={flagState}
            onChange={(e) => setFlagState(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* 航行区域 */}
        <div>
          <span className="block text-sm font-medium">
            航行区域 <span className="text-red-500">*</span>
          </span>
          <div className="mt-1 space-y-1">
            {navAreas.map((area) => (
              <label key={area} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={navigationArea.includes(area)}
                  onChange={(e) =>
                    handleNavAreaChange(area, e.target.checked)
                  }
                />
                {NAV_AREA_LABELS[area]}
              </label>
            ))}
          </div>
        </div>

        {/* 航路 */}
        <div>
          <label htmlFor="routes" className="block text-sm font-medium">
            航路（カンマ区切り）
          </label>
          <input
            id="routes"
            type="text"
            value={routes}
            onChange={(e) => setRoutes(e.target.value)}
            placeholder="例: 東京-シンガポール, 横浜-ロサンゼルス"
            className={inputClass}
          />
        </div>

        {/* IMO番号 */}
        <div>
          <label htmlFor="imo_number" className="block text-sm font-medium">
            IMO番号
          </label>
          <input
            id="imo_number"
            type="text"
            pattern="\d{7}"
            maxLength={7}
            title="IMO番号は7桁の数字です"
            value={imoNumber}
            onChange={(e) => setImoNumber(e.target.value)}
            className={inputClass}
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "登録中..." : "[SAVE] 船舶を登録"}
        </button>
      </form>
    </div>
  );
}

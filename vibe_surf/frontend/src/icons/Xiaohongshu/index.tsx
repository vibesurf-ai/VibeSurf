import type React from "react";
import { forwardRef } from "react";
import SvgXiaohongshu from "./Xiaohongshu";

export const XiaohongshuIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgXiaohongshu ref={ref} {...props} />;
});
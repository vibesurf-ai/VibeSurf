import React, { forwardRef } from "react";
import SvgZhihu from "./Zhihu";

export const ZhihuIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgZhihu ref={ref} {...props} />;
});
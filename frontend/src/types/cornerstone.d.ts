/**
 * Cornerstone 系列模块的轻量类型声明
 * 真实库无 @types 包，这里只为编译通过提供最小定义
 */

declare module 'cornerstone-core' {
  export interface CornerstoneImage {
    imageId: string
    width: number
    height: number
    [key: string]: any
  }
  export interface Viewport {
    scale: number
    translation: { x: number; y: number }
    voi: { windowWidth: number; windowCenter: number }
    invert: boolean
    rotation: number
    hflip: boolean
    vflip: boolean
    [key: string]: any
  }

  export function enable(element: HTMLElement, options?: any): void
  export function disable(element: HTMLElement): void
  export function loadImage(imageId: string): Promise<CornerstoneImage>
  export function loadAndCacheImage(imageId: string): Promise<CornerstoneImage>
  export function displayImage(
    element: HTMLElement,
    image: CornerstoneImage,
    viewport?: Partial<Viewport>
  ): void
  export function getEnabledElement(element: HTMLElement): any
  export function getViewport(element: HTMLElement): Viewport
  export function setViewport(element: HTMLElement, viewport: Partial<Viewport>): void
  export function reset(element: HTMLElement): void
  export function resize(element: HTMLElement, forceFitToWindow?: boolean): void
  export function pageToPixel(element: HTMLElement, x: number, y: number): { x: number; y: number }
  export function pixelToCanvas(element: HTMLElement, point: { x: number; y: number }): { x: number; y: number }
  export const events: any
  export const external: any
  export const imageCache: any

  const cornerstone: any
  export default cornerstone
}

declare module 'cornerstone-tools' {
  export function init(options?: any): void
  export function addTool(tool: any, options?: any): void
  export function setToolActive(toolName: string, options?: any): void
  export function setToolPassive(toolName: string): void
  export function setToolEnabled(toolName: string): void
  export function setToolDisabled(toolName: string): void
  export function clearToolState(element: HTMLElement, toolName: string): void
  export function getToolState(element: HTMLElement, toolName: string): any
  export function addToolState(element: HTMLElement, toolName: string, data: any): void
  export const external: any
  export const PanTool: any
  export const ZoomTool: any
  export const ZoomMouseWheelTool: any
  export const WwwcTool: any
  export const LengthTool: any
  export const AngleTool: any
  export const RectangleRoiTool: any
  export const FreehandRoiTool: any
  export const EraserTool: any
  export const ProbeTool: any

  const cornerstoneTools: any
  export default cornerstoneTools
}

declare module 'cornerstone-web-image-loader' {
  export const external: any
  export function configure(options: any): void
  const cornerstoneWebImageLoader: {
    external: any
    configure: (options: any) => void
    [key: string]: any
  }
  export default cornerstoneWebImageLoader
}

declare module 'cornerstone-math' {
  const cornerstoneMath: any
  export default cornerstoneMath
}

declare module 'hammerjs' {
  const Hammer: any
  export default Hammer
}

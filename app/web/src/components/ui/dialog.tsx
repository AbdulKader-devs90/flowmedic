import type { ComponentProps } from 'react'
import * as Primitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/lib/utils'
export const Dialog=Primitive.Root
export const DialogTrigger=Primitive.Trigger
export const DialogPortal=Primitive.Portal
export const DialogClose=Primitive.Close
export const DialogTitle=Primitive.Title
export const DialogDescription=Primitive.Description
export function DialogHeader({ className,...props }: ComponentProps<'div'>) { return <div className={cn('space-y-2',className)} {...props} /> }
export function DialogFooter({ className,...props }: ComponentProps<'div'>) { return <div className={cn('flex-row justify-end',className)} {...props} /> }
export function DialogOverlay() { return <Primitive.Overlay className="overlay" /> }
export function DialogContent({ children,className,showCloseButton=true,...props }: ComponentProps<typeof Primitive.Content> & { showCloseButton?: boolean }) { const reduced=useReducedMotion(); return <Primitive.Portal><DialogOverlay /><Primitive.Content className={cn('dialog',className)} {...props}><motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ duration:reduced ? 0 : .2 }}>{children}</motion.div>{showCloseButton && <Primitive.Close aria-label="Close dialog" className="icon-button absolute right-4 top-4"><X /></Primitive.Close>}</Primitive.Content></Primitive.Portal> }
